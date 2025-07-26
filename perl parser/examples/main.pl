#!/usr/bin/perl
use strict;
use warnings;
use FindBin;
use lib "$FindBin::Bin/../lib";

use Employee::Manager;

my $manager = Employee::Manager->new();

print "Employee Manager CLI\n";
print "1. Add Employee\n2. List Employees\n3. Find Employee\n4. Delete Employee\n5. Exit\n";

while (1) {
    print "\nChoose an option: ";
    chomp(my $choice = <STDIN>);
    if ($choice == 1) {
        print "Enter Name: "; chomp(my $name = <STDIN>);
        print "Enter Age: ";  chomp(my $age = <STDIN>);
        $manager->add_employee($name, $age);
    } elsif ($choice == 2) {
        $manager->list_employees();
    } elsif ($choice == 3) {
        print "Enter ID to search: "; chomp(my $id = <STDIN>);
        $manager->find_employee($id);
    } elsif ($choice == 4) {
        print "Enter ID to delete: "; chomp(my $id = <STDIN>);
        $manager->delete_employee($id);
    } elsif ($choice == 5) {
        print "Exiting...\n"; last;
    } else {
        print "Invalid option!\n";
    }
}
