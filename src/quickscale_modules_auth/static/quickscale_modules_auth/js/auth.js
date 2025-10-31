/**
 * QuickScale Auth Module JavaScript
 * Client-side form validation and UX enhancements
 */

document.addEventListener('DOMContentLoaded', function() {
    // Auto-dismiss messages after 5 seconds
    const messages = document.querySelectorAll('.alert');
    messages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            setTimeout(function() {
                message.remove();
            }, 300);
        }, 5000);
    });

    // Password strength indicator (basic)
    const passwordFields = document.querySelectorAll('input[type="password"]');
    passwordFields.forEach(function(field) {
        if (field.name.includes('password1') || field.name === 'new_password1') {
            field.addEventListener('input', function() {
                const strength = calculatePasswordStrength(this.value);
                updatePasswordStrength(this, strength);
            });
        }
    });

    // Email normalization
    const emailFields = document.querySelectorAll('input[type="email"]');
    emailFields.forEach(function(field) {
        field.addEventListener('blur', function() {
            this.value = this.value.toLowerCase().trim();
        });
    });

    // Confirm account deletion
    const deleteForm = document.querySelector('form[action*="delete"]');
    if (deleteForm) {
        deleteForm.addEventListener('submit', function(e) {
            if (!confirm('Are you absolutely sure you want to delete your account? This action cannot be undone.')) {
                e.preventDefault();
            }
        });
    }
});

/**
 * Calculate password strength
 */
function calculatePasswordStrength(password) {
    let strength = 0;

    if (password.length >= 8) strength++;
    if (password.length >= 12) strength++;
    if (/[a-z]/.test(password) && /[A-Z]/.test(password)) strength++;
    if (/\d/.test(password)) strength++;
    if (/[^a-zA-Z0-9]/.test(password)) strength++;

    return strength;
}

/**
 * Update password strength indicator
 */
function updatePasswordStrength(field, strength) {
    // Remove existing indicator
    let indicator = field.parentElement.querySelector('.password-strength');
    if (indicator) {
        indicator.remove();
    }

    // Add new indicator
    if (field.value.length > 0) {
        indicator = document.createElement('div');
        indicator.className = 'password-strength';
        indicator.style.marginTop = '0.5rem';
        indicator.style.fontSize = '0.875rem';

        if (strength < 2) {
            indicator.textContent = '⚠️ Weak password';
            indicator.style.color = '#dc3545';
        } else if (strength < 4) {
            indicator.textContent = '✓ Moderate password';
            indicator.style.color = '#ffc107';
        } else {
            indicator.textContent = '✓ Strong password';
            indicator.style.color = '#28a745';
        }

        field.parentElement.appendChild(indicator);
    }
}
