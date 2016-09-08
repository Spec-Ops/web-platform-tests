/* globals Promise, done, assert_true, on_event */

/**
 * Creates an ATTAconn object.  If the parameters are supplied
 * it sets up event listeners to send the test data to an ATTA if one
 * is available.  If the ATTA does not respond, it will assume the test 
 * is being done manually and the results are being entered in the 
 * parent test window.
 *
 * @constructor
 * @param {object} params
 * @param {string} [params.test] - object containing JSON test definition
 * @param {string} [params.testFile] - URI of a file with JSON test definition
 * @param {string} params.ATTAuri - URI to use to exercise the window
 * @event DOMContentLoaded Calls init once DOM is fully loaded
 * @returns {object} Reference to the new object
 *
 */

function ATTAconn(params) {
  'use strict';

  this.Params = null;       // parameters passed in
  this.Promise = null;      // master Promise that resolves when intialization is complete
  this.Properties = null;   // testharness_properties from the opening window
  this.Test = null;         // test being run

  this.loading = true;

  this.timeout = 5000;

  var pending = [] ;

  // set up in case DOM finishes loading early
  pending.push(new Promise(function(resolve) {
    on_event(document, "DOMContentLoaded", function() {
        resolve(true);
    }.bind(this));
  }.bind(this)));

  // if we are under runner, then there are props in the parent window
  //
  // if "output" is set in that, then pause at the end of running so the output
  // can be analyzed. @@@TODO@@@
  if (window && window.opener && window.opener.testharness_properties) {
    this.Properties = window.opener.testharness_properties;
  }

  this.Params = params;

  if (this.Params.hasOwnProperty("ATTAuri")) {
    this.ATTAuri = this.Params.ATTAuri;
  } else {
    this.ATTAuri = "http://localhost:12345/ATTA";
  }

  // start by loading the test (it might be inline, but
  // loadTest deals with that
  pending.push(this.loadTest(params)
    .then(function(test) {
      // if the test is NOT an object, turn it into one
      if (typeof test === 'string') {
        test = JSON.parse(test) ;
      }

      this.Test = test;

      // Test should have information that we can put in the template

      if (test.description) {
        this.DescriptionText = test.description;
      }

    }));

  this.Promise = new Promise(function(resolve, reject) {
    // once the DOM and the test is loaded... set us up
    Promise.all(pending)
    .then(function() {
      // Everything is loaded
      this.loading = false ;
      // initialize the various listeners
      this.init();
      resolve(this);
    }.bind(this))
    .catch(function(err) {
      // loading the components failed somehow - report the errors and mark the test failed
      test( function() {
        assert_true(false, "Loading of test components failed: " +JSON.stringify(err)) ;
      }, "Loading test components");
      done() ;
      reject("Loading of test components failed: "+JSON.stringify(err));
      return ;
    }.bind(this));
  }.bind(this));

  return this;
}

ATTAconn.prototype = {

  /**
   * @listens click
   */
  init: function() {
    'use strict';
    if (!this.loading) {
      // everything is ready.  Let's talk to the message
      this.startTest().then(function(res) {
        // automation environment connection worked
        if (res.body.hasOwnProperty("status")) {
          if (res.body.status === "READY") {
            // the system is ready for us - let's do a test!
            if (res.body.hasOwnProperty("API")) {
              var API = res.body.API;
              if (this.Test.hasOwnProperty(API)) {
                // we actually have a test for this API
                test(function() {
                  this.runTests(res.Test[API]);
                }.bind(this), this.Test.title);
                this.endTest().then(function() {
                  done();
                }.bind(this));
              } else {
                // we don't know this API for this test
                this.setupManualTest("Unknown AT API: " + API);
              }
            } else {
              this.setupManualTest("No API in response from ATTA");
            }
          } else {
            // the system reported soemthing else - fail out with the statusText as a result
            this.setupManualTest("ATTA reported an error: " + res.body.statusText);
          }
        } else {
          this.setupManualTest("ATTA did not report a status");
        }
      }.bind(this))
      .catch(function(res) {
        // start failed so just sit and wait for a manual test to occur
        if (res.timeout) {
          this.setupManualTest("No response from ATTA at " + this.ATTAuri);
        } else {
          this.setupManualTest("Error from ATTA: " + res.status + ": " + res.statusText);
        }
      }.bind(this));
    } else {
      window.alert("Loading did not finish before init handler was called!");
    }
  },

  setupManualTest: function(message) {
    // if we determine the test should run manually, then expose all of the conditions that are
    // in the TEST data structure so that a human can to the inspection and calculate the result
    'use strict';
    window.alert(message);
  },

  // runTests - process subtests
  /**
   * @param {object} assertions - List of assertions to process
   * @param {string} content - JSON(-LD) to be evaluated
   * @param {string} [testAction='continue'] - state of test processing (in parent when recursing)
   * @param {integer} [level=0] - depth of recursion since assertion lists can nest
   * @param {string} [compareWith='and'] - the way the results of the referenced assertions should be compared
   * @returns {string} - the testAction resulting from evaluating all of the assertions
   */
  runTests: function(API) {
    'use strict';

    return new Promise(function(resolve, reject) {
      var theTests = [] ;
      if (this.Test && API !== undefined && API !== "") {
        // we have assertions for this API
        var testNum = 0;
        this.Test[API].forEach( function(assertion) {
          // send that test to the server
          testNum++;
          theTests.push(this.sendTest(assertion).then(function(res) {
            if (res.result === "ERROR") {
              // special condition that means something BAD happened
              window.alert("Something bad happened: " + res.message);
            } else if (res.result === "PASS") {
              assert_true(true);
            } else if (res.result === "FAIL") {
              assert_true(false, "" + testNum + ": " + res.message);
            }
          }.bind(this))
          .catch(function(res) {
            assert_true(false, "" + testNum + ": " + res.statusText);
          }.bind(this))
          );
        }.bind(this));
      }
      Promise.all(theTests)
      .then(function(res) {
        resolve(res);
      }.bind(this))
      .catch(function(res) {
        reject(res);
      }.bind(this));
    }.bind(this));
  },

  // loadTest - load a test from an external JSON file
  //
  // returns a promise that resolves with the contents of the
  // test

  loadTest: function(params) {
    'use strict';

    if (params.hasOwnProperty('testFile')) {
      // the test is referred to by a file name
      return this._fetch("GET", params.testFile);
    } // else
    return new Promise(function(resolve, reject) {
      if (params.hasOwnProperty('test')) {
        resolve(params.test);
      } else {
        reject("Must supply a 'test' or 'testFile' parameter");
      }
    });
  },

  // startTest - send the test start message
  //
  // Returns a promise that resolves when when the ATTA replies with READY

  startTest: function() {
    'use strict';

    return this._fetch("POST", this.ATTAuri + "/start", null, { 
      test: this.testName,
      title: window.title
    });
  },

  // sendTest - send test data to an ATTA and wait for a response
  //
  // returns a promise that resolves with the results of the test

  sendTest: function(testData) {
    'use strict';

    if (typeof testData !== "string") {
      testData = JSON.stringify(testData);
    }
    return this._fetch("POST", this.ATTAuri + "/test", null, testData, true);
  },

  endTest: function() {
    'use strict';

    return this._fetch("GET", this.ATTAuri + "/end");
  },

  // _fetch - return a promise after sending data
  //
  // Resolves with the returned information in a structure
  // including:
  //
  // xhr - a raw xhr object
  // headers - an array of headers sent in the request
  // status - the status code
  // statusText - the text of the return status
  // text - raw returned data
  // body - an object parsed from the returned content 
  //

  _fetch: function (method, url, headers, content, parse) {
    'use strict';
    if (method === undefined) {
      method = "GET";
    }
    if (parse === undefined) {
      parse = true;
    }

    // note that this Promise always resolves - there is no reject
    // condition
    
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();

      // this gets returned when the request completes
      var resp = {
        xhr: xhr,
        headers: null,
        status: 0,
        statusText: "",
        body: null,
        text: ""
      };

      xhr.open(method, url);

      // headers?
      if (headers !== undefined) {
        headers.forEach(function(ref) {
          xhr.setRequestHeader(ref[0], ref[1]);
        });
      }

      if (this.timeout) {
        xhr.timeout = this.timeout;
      }

      xhr.ontimeout = function() {
        resp.timeout = this.timeout;
        resolve(resp);
      };

      xhr.onerror = function() {
        resolve(resp);
      };

      xhr.onload = function () {
        resp.status = this.status;
        if (this.status >= 200 && this.status < 300) {
          var d = xhr.response;
          // return the raw text of the response
          resp.text = d;
          // we have it; what is it?
          if (parse) {
            try {
              d = JSON.parse(d);
              resp.body = d;
            }
            catch(err) {
              resp.body = null;
            }
          }
          resolve(resp);
        } else {
          reject({
            status: this.status,
            statusText: xhr.statusText
          });
        }
      };

      if (content !== undefined) {
        if ("object" === typeof(content)) {
          xhr.send(JSON.stringify(content));
        } else if ("function" === typeof(content)) {
          xhr.send(content());
        } else if ("string" === typeof(content)) {
          xhr.send(content);
        }
      } else {
        xhr.send();
      }
    });
  },

};
