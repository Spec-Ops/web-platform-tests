#!/usr/bin/perl
#
#  make-tests.pl - generate WPT test cases from the testable statements wiki
#
#

use strict;

use IO::String ;
use JSON ;
use MediaWiki::API ;

# general logic:
#
# retrieve the wiki page in JSON format
#

my @apiNames = qw(UIA MSAA ATK IAccessible2 AXAPI);

my $dir = "../raw";

my $page = "ARIA_1.1_Testable_Statements";

my $wiki_config = {
  "api_url" => "https://www.w3.org/wiki/api.php"
};

my $MW = MediaWiki::API->new( $wiki_config );

my $page = $MW->get_page( { title => $page } );

my $theContent = $page->{'*'};

# Now let's walk through the content and build a test page for every item
#

# iterate over the content

my $io = IO::String->new($theContent);
# my $io ;
# open($io, "<", "raw") ;

my $state = 0;   # between items
my $current = "";
my $theCode = "";
my $theAsserts = {} ;
my $theAssertCount = 0;
my $theAPI = "";
my $typeRows = 0;
my $theType = "";

while (<$io>) {
  # look for state
  if (m/^=== (.*) ===/) {
    if ($state != 0) {
      # we were in an item; dump it
      build_test($current, $theCode, $theAsserts) ;
      print "Finished $current\n";
    }
    $state = 1;
    $current = $1;
    $theCode = "";
    $theAsserts = {};
  }
  if ($state == 1) {
    if (m/<pre>/) {
      # we are now in the code block
      $state = 2;
    }
  }
  if ($state == 2) {
    if (m/<\/pre>/) {
      # we are done with the code block
      $state = 3;
    } else  {
      if (m/^\s/) {
        $theCode .= $_;
      }
    }
  } elsif ($state == 3) {
    # look for a table
    if (m/^\{\|/) {
      # table started
      $state = 4;
    }
  } elsif ($state == 4) {
    if (m/^\|-/) {
      if ($theAPI
          && exists($theAsserts->{$theAPI}->[$theAssertCount])
          && scalar(@{$theAsserts->{$theAPI}->[$theAssertCount]})) {
        $theAssertCount++;
      }
      # start of a table row
      if ($theType ne "" && $typeRows) {
        print qq($theType typeRows was $typeRows\n);
        # we are still processing items for a type
        $typeRows--;
        # populate the first cell
        $theAsserts->{$theAPI}->[$theAssertCount] = [ $theType ] ;
      } else {
        $theType = "";
      }
    } elsif (m/^\|\}/) {
      # ran out of table
      $state = 5;
    } elsif (m/^\|rowspan="*([0-9])"*\|(.*)$/) {
      my $rows = $1;
      my $theString = $2;
      $theString =~ s/ +$//;
      $theString =~ s/^ +//;
      if (grep { $_ eq $theString } @apiNames) {
        $theAssertCount = 0;
        # this is a new API section
        $theAPI = $theString ;
        $theAsserts->{$theAPI} = [ [] ] ;
        $theType = "";
      } else {
        # this is a multi-row type
        $theType = $theString;
        $typeRows = $rows;
        print qq(Found multi-row $theString for $theAPI with $typeRows rows\n);
        $typeRows--;
        # populate the first cell
        if ($theAPI
            && exists($theAsserts->{$theAPI}->[$theAssertCount])
            && scalar(@{$theAsserts->{$theAPI}->[$theAssertCount]})) {
          $theAssertCount++;
        }
        $theAsserts->{$theAPI}->[$theAssertCount] = [ $theType ] ;
      }
    } elsif (m/^\|(.*)$/) {
      my $item = $1;
      $item =~ s/^ *//;
      $item =~ s/ *$//;
      $item =~ s/^['"]//;
      $item =~ s/['"]$//;
      # add into the data structure for the API
      if (!exists $theAsserts->{$theAPI}->[$theAssertCount]) {
        $theAsserts->{$theAPI}->[$theAssertCount] = [ $item ] ;
      } else {
        push(@{$theAsserts->{$theAPI}->[$theAssertCount]}, $item);
      }
    }
  }
};

if ($state != 0) {
  build_test($current, $theCode, $theAsserts) ;
  print "Finished $current\n";
}

exit 0;


sub build_test() {
  my $title = shift ;
  my $code = shift ;
  my $asserts = shift;

  if ($title eq "") {
    print "No name provided!";
    return;
  }

  if ($code eq "") {
    print "No code for $title; skipping.\n";
    return;
  }

  if ( $asserts eq {}) {
    print "No code or assertions for $title; skipping.\n";
    return;
  }

  $asserts->{WAIFAKE} = [ [ "role", "ROLE_TABLE_CELL" ], [ "interface", "TableCell" ] ];

  # massage the data to make it more sensible
  if (exists $asserts->{"ATK"}) {
    print "processing ATK for $title\n";
    my @conditions = @{$asserts->{"ATK"}};
    for (my $i = 0; $i < scalar(@conditions); $i++) {
      my @new = ();
      my $start = 0;
      my $assert = "true";
      if ($conditions[$i]->[0] =~ m/^NOT/) {
        $start = 1;
        $assert = "false";
      }

      print qq(Looking at $title $conditions[$i]->[$start]\n);
      if ($conditions[$i]->[$start] =~ m/^ROLE_/) {
        $new[0] = "role";
        $new[1] = $conditions[$i]->[$start];
        $new[2] = $assert;
      } elsif ($conditions[$i]->[$start] =~ m/(.*) interface/i) {
        $new[0] = "interface";
        $new[1] = $1;
        print "$1 condition is " . $conditions[$i]->[1] . "\n";
        if ($conditions[$i]->[1] ne '<shown>'
          && $conditions[$i]->[1] !~ m/true/i ) {
          $assert = "false";
        }
        $new[2] = $assert;
      } elsif ($conditions[$i]->[$start] eq "object" || $conditions[$i]->[$start] eq "attribute" ) {
        $new[0] = "attribute";
        my $val = $conditions[$i]->[2];
        $val =~ s/"//g;
        $new[1] = $conditions[$i]->[1] . ":" . $val;
        if ($conditions[$i]->[3] eq "not exposed"
            || $conditions[$i]->[3] eq "false") {
          $new[2] = "false";
        } else {
          $new[2] = "true";
        }
      } elsif ($conditions[$i]->[$start] =~ m/^STATE_/) {
        $new[0] = "state";
        $new[1] = $conditions[$i]->[$start];
        $new[2] = $assert;
      } elsif ($conditions[$i]->[$start] =~ m/^object attribute (.*)/) {
        my $name = $1;
        $new[0] = "attribute";
        my $val = $conditions[$i]->[1];
        $val =~ s/"//g;
        if ($val eq "not exposed" || $val eq "not mapped") {
          $new[1] = $name;
          $new[2] = "false";
        } else {
          $new[1] = $name . ":" . $val;
          $new[2] = "true";
        }
      } else {
        @new = @{$conditions[$i]};
        if ($conditions[$i]->[2] eq '<shown>') {
          $new[2] = "true";
        }
      }
      $conditions[$i] = \@new;
    }
    $asserts->{"ATK"} = \@conditions;
  }


  my $asserts_json = to_json($asserts, { pretty => 1, utf8 => 1});

  my $fileName = $title;
  $fileName =~ s/\s*$//;
  $fileName =~ s/"//g;
  $fileName =~ s/\///g;
  $fileName =~ s/\s+/_/g;
  $fileName =~ s/=/_/g;
  $fileName .= "-manual.html";

  my $template = qq(<!doctype html>
<html>
<head>
<title>$title</title>
<link rel="stylesheet" href="/resources/testharness.css">
<script src="/resources/testharness.js"></script>
<script src="/resources/testharnessreport.js"></script>
<script src="/wai-aria/scripts/ATTAcomm.js"></script>
<script>
setup({explicit_timeout: true, explicit_done: true });

var theTest = new ATTAcomm(
    { "title": '$title',
      "steps": [
        {
          "type":  "test",
          "title": "step 1",
          "element": "test",
          "test" : $asserts_json
        }
    ]
  }
) ;
</script>
</head>
<body>
<p>This test examines the ARIA properties for $title.</p>
$code
<div id="ATTAmessages"></div>
<div id="manualMode"></div>
</body>
</html>
);

  my $file ;

  if (open($file, ">", "$dir/$fileName")) {
    print $file $template;
    close $file;
  } else {
    print qq(Failed to create file "$dir/$fileName" $!\n);
  }

  return;
}


