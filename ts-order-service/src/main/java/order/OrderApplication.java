package order;

import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.contrib.providers.flagd.FlagdProvider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

import javax.annotation.PostConstruct;


import dev.openfeature.sdk.OpenFeatureAPI;
import dev.openfeature.contrib.providers.flagd.FlagdProvider;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.cloud.client.loadbalancer.LoadBalanced;
import org.springframework.context.annotation.Bean;
import org.springframework.web.client.RestTemplate;

import javax.annotation.PostConstruct;

@SpringBootApplication
public class OrderApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderApplication.class, args);
    }

    @LoadBalanced
    @Bean
    public RestTemplate restTemplate(RestTemplateBuilder builder) {
        return builder.build();
    }

    @PostConstruct
    public void initializeFeatureFlags() {
        try {
            String flagdHost = System.getenv().getOrDefault("FLAGD_HOST", "flagd");
            int flagdPort = Integer.parseInt(System.getenv().getOrDefault("FLAGD_PORT", "8013"));

            FlagdProvider provider = new FlagdProvider();
            OpenFeatureAPI.getInstance().setProvider(provider);

        } catch (Exception e) {
            // silently ignore
        }
    }
}

