package cancel.controller;

import cancel.service.CancelService;
import cancel.service.FeatureFlagService;
import edu.fudan.common.util.Response;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import static org.springframework.http.ResponseEntity.ok;

/**
 * @author fdse
 */
@RestController
@RequestMapping("/api/v1/cancelservice")
public class CancelController {

    @Autowired
    CancelService cancelService;

    @Autowired
    FeatureFlagService featureFlagService;

    private static final Logger LOGGER = LoggerFactory.getLogger(CancelController.class);

    @GetMapping(path = "/welcome")
    public String home(@RequestHeader HttpHeaders headers) {
        return "Welcome to [ Cancel Service ] !";
    }

    @CrossOrigin(origins = "*")
    @GetMapping(path = "/cancel/refound/{orderId}")
    public HttpEntity calculate(@PathVariable String orderId, @RequestHeader HttpHeaders headers) {
        CancelController.LOGGER.info("[calculate][Calculate Cancel Refund][OrderId: {}]", orderId);
        return ok(cancelService.calculateRefund(orderId, headers));
    }

    @CrossOrigin(origins = "*")
    @GetMapping(path = "/cancel/{orderId}/{loginId}")
    public HttpEntity cancelTicket(@PathVariable String orderId, @PathVariable String loginId,
                                   @RequestHeader HttpHeaders headers) {

        CancelController.LOGGER.info("[cancelTicket][Cancel Ticket][info: {}]", orderId);
        try {
            CancelController.LOGGER.info("[cancelTicket][Cancel Ticket, Verify Success]");
            return ok(cancelService.cancelOrder(orderId, loginId, headers));
        } catch (Exception e) {
            CancelController.LOGGER.error(e.getMessage());
            return ok(new Response<>(1, "error", null));
        }
    }

    /**
     * Testing endpoint to check feature flag values
     * Usage: GET /api/v1/cancelservice/test/flag/{flagName}
     * Example: GET /api/v1/cancelservice/test/flag/tt-feat-01
     */
    @CrossOrigin(origins = "*")
    @GetMapping(path = "/test/flag/{flagName}")
    public HttpEntity testFlag(@PathVariable String flagName, @RequestHeader HttpHeaders headers) {

        try {
            boolean flagValue = featureFlagService.isEnabled(flagName);

            // Create a simple response with flag info
            String message = String.format("Flag '%s' is %s", flagName, flagValue ? "ENABLED" : "DISABLED");

            Response<String> response = new Response<>();
            response.setStatus(1);  // Success
            response.setMsg(message);
            response.setData(String.valueOf(flagValue));

            return ok(response);

        } catch (Exception e) {
            CancelController.LOGGER.error("[testFlag][Error: {}]", e.getMessage());

            Response<String> errorResponse = new Response<>();
            errorResponse.setStatus(0);  // Error
            errorResponse.setMsg("Error testing flag: " + e.getMessage());
            errorResponse.setData("false");

            return ok(errorResponse);
        }
    }

}
