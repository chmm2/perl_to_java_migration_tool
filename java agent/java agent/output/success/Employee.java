import java.util.HashMap;
import java.util.Map;

public class Employee {
    private Map<String, Object> details;

    public Employee(String classType, Map<String, Object> args) {
        this.details = new HashMap<>();
        this.details.putAll(args);
    }

    public String getDetails() {
        return this.details.toString();
    }

    public String id() {
        return (String) this.details.get("id");
    }
}