import java.util.stream.Stream;
import java.util.function.Supplier;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentMap;
import java.util.List;
import java.util.Map;
import java.util.LinkedHashMap;
import java.util.LinkedList;
import java.util.Collections;
import java.io.Closeable;
import java.io.IOException;

public class Main {

    private static final AtomicReference<Main> INSTANCE = new AtomicReference<>();

    private final Map<String, String> cache = new ConcurrentHashMap<>();

    private Main() {
    }

    public static Main getInstance() {
        Main instance = INSTANCE.get();
        if (instance == null) {
            instance = new Main();
            if (!INSTANCE.compareAndSet(null, instance)) {
                instance = INSTANCE.get();
            }
        }
        return instance;
    }

    public void defaultMethod() {
        try (Closeable resource = new Closeable() {
            @Override
            public void close() throws IOException {
            }
        }) {
            String result = Optional.ofNullable(cache.get("key"))
                    .orElseGet(() -> {
                        String computedValue = computeExpensiveValue();
                        cache.put("key", computedValue);
                        return computedValue;
                    });
            System.out.println(result);
        } catch (IOException e) {
            throw new RuntimeException(e);
        }
    }

    private String computeExpensiveValue() {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < 100; i++) {
            builder.append("Value ").append(i).append("\n");
        }
        return builder.toString();
    }
}