package Employee::Manager;
use strict;
use warnings;
use Storable qw(store retrieve);
use File::Spec;
use lib '..';
use Employee::Employee;

my $DB_FILE = File::Spec->catfile(File::Spec->curdir(), 'data', 'employees.db');

sub new {
    my $class = shift;
    my $self = {
        employees => -e $DB_FILE ? retrieve($DB_FILE) : {},
        next_id   => 1,
    };
    $self->{next_id} = (sort { $b <=> $a } keys %{$self->{employees}})[0] + 1 if %{$self->{employees}};
    return bless $self, $class;
}

sub add_employee {
    my ($self, $name, $age) = @_;
    my $id = $self->{next_id}++;
    my $employee = Employee::Employee->new(id => $id, name => $name, age => $age);
    $self->{employees}{$id} = $employee;
    $self->_save();
    print "Employee added with ID $id\n";
}

sub list_employees {
    my $self = shift;
    foreach my $emp (values %{$self->{employees}}) {
        print $emp->get_details(), "\n";
    }
}

sub find_employee {
    my ($self, $id) = @_;
    if (my $emp = $self->{employees}{$id}) {
        print $emp->get_details(), "\n";
    } else {
        print "Employee not found!\n";
    }
}

sub delete_employee {
    my ($self, $id) = @_;
    if (delete $self->{employees}{$id}) {
        $self->_save();
        print "Employee deleted.\n";
    } else {
        print "Employee not found.\n";
    }
}

sub _save {
    my $self = shift;
    store($self->{employees}, $DB_FILE);
}

1;
