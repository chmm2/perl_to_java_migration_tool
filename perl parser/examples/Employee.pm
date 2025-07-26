package Employee::Employee;
use strict;
use warnings;

sub new {
    my ($class, %args) = @_;
    return bless {
        id   => $args{id},
        name => $args{name},
        age  => $args{age},
    }, $class;
}

sub get_details {
    my $self = shift;
    return "ID: $self->{id}, Name: $self->{name}, Age: $self->{age}";
}

sub id { 
    shift->{id} 
}

1;
