package cancel.async;

import cancel.service.FeatureFlagService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;

import java.util.concurrent.Future;
import java.util.concurrent.CompletableFuture;

@Component
public class AsyncTask {

    @Autowired
    private FeatureFlagService featureFlagService;

    @Async("mySimpleAsync")
    public Future<Boolean> drawBackMoneyForOrderCancel(String money, String userId, String orderId, String loginToken) throws InterruptedException {

        System.out.println("[TrainTicket][Cancel][AsyncTask] Starting drawback process for order: " + orderId);

        if (featureFlagService.isEnabled("tt-feat-01")) {
            Thread.sleep(8000);
        }

        System.out.println("[TrainTicket][Cancel][AsyncTask] Processing payment drawback...");
        System.out.println("[TrainTicket][Cancel][AsyncTask] Money: " + money + ", User: " + userId);

        try {
            Thread.sleep(1000);
            System.out.println("[TrainTicket][Cancel][AsyncTask] Payment drawback completed successfully");
            return CompletableFuture.completedFuture(true);
        } catch (Exception e) {
            System.err.println("[TrainTicket][Cancel][AsyncTask] Payment drawback failed: " + e.getMessage());
            return CompletableFuture.completedFuture(false);
        }
    }

    @Async("mySimpleAsync")
    public Future<Boolean> sendEmail(String email, String orderId) {

        featureFlagService.isEnabled("tt-feat-01");

        System.out.println("[TrainTicket][Cancel][AsyncTask] Sending cancellation email to: " + email);
        System.out.println("[TrainTicket][Cancel][AsyncTask] Order ID: " + orderId);

        try {
            Thread.sleep(500);
            System.out.println("[TrainTicket][Cancel][AsyncTask] Email sent successfully");
            return CompletableFuture.completedFuture(true);
        } catch (Exception e) {
            System.err.println("[TrainTicket][Cancel][AsyncTask] Email sending failed: " + e.getMessage());
            return CompletableFuture.completedFuture(false);
        }
    }
}
