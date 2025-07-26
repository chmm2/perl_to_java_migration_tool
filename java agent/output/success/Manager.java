import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.stream.Collectors;

public class EmployeeManager {
    private final Map<String, Employee> employees;
    private final Map<String, Object> args;

    public EmployeeManager(String className, Map<String, Object> args) {
        this.args = args;
        this.employees = new LinkedHashMap<>();
    }

    public EmployeeManager addEmployee(Employee employee) {
        employees.put(employee.getId(), employee);
        return this;
    }

    public List<Employee> listEmployees() {
        return new ArrayList<>(employees.values());
    }

    public Optional<Employee> findEmployee(String employeeId) {
        return Optional.ofNullable(employees.get(employeeId));
    }

    public EmployeeManager deleteEmployee(String employeeId) {
        employees.remove(employeeId);
        return this;
    }

    private void save() {
    }

    public static class Employee {
        private final String id;

        public Employee(String id) {
            this.id = id;
        }

        public String getId() {
            return id;
        }

        @Override
        public boolean equals(Object o) {
            if (this == o) return true;
            if (o == null || getClass() != o.getClass()) return false;
            Employee employee = (Employee) o;
            return id.equals(employee.id);
        }

        @Override
        public int hashCode() {
            return id.hashCode();
        }
    }
}