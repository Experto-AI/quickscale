/**
 * Plan selection component for handling pricing display
 * and plan selection options.
 */
// Removed Alpine.js planSelection component definition

// Handle plan selection button clicks
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.select-plan-button').forEach(button => {
        button.addEventListener('click', function() {
            const planId = this.getAttribute('data-plan-id');
            
            // Redirect based on authentication status without billing interval
            if (isAuthenticated) {
                // Redirect authenticated users to checkout
                window.location.href = '/checkout/?plan=' + planId;
            } else {
                // Redirect anonymous users to signup with plan info
                window.location.href = '/signup/?plan=' + planId;
            }
        });
    });
});
