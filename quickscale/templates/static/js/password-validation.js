/**
 * Password validation and strength meter for QuickScale
 */
document.addEventListener('DOMContentLoaded', function() {
    // Find password fields in the page
    const passwordFields = document.querySelectorAll('input[type="password"][name="password1"], input[type="password"][name="new_password1"]');
    
    passwordFields.forEach(function(passwordField) {
        // Only proceed if we found a password field
        if (!passwordField) return;
        
        // Create strength meter elements
        const strengthContainer = document.createElement('div');
        strengthContainer.className = 'password-strength mt-2';
        strengthContainer.innerHTML = `
            <div class="strength-meter">
                <div class="strength-meter-fill" style="width: 0%"></div>
            </div>
            <div class="strength-text has-text-grey is-size-7">Password strength: Too weak</div>
        `;
        
        // Insert after the password field
        passwordField.parentNode.insertBefore(strengthContainer, passwordField.nextSibling);
        
        const strengthMeterFill = strengthContainer.querySelector('.strength-meter-fill');
        const strengthText = strengthContainer.querySelector('.strength-text');
        
        // Add event listener to password field
        passwordField.addEventListener('input', function() {
            const password = this.value;
            const strength = calculatePasswordStrength(password);
            
            // Update the strength meter
            strengthMeterFill.style.width = strength.score + '%';
            strengthText.textContent = 'Password strength: ' + strength.label;
            
            // Set colors based on strength
            strengthMeterFill.className = 'strength-meter-fill ' + strength.className;
        });
    });
    
    // Function to calculate password strength
    function calculatePasswordStrength(password) {
        // Initialize score
        let score = 0;
        let feedback = [];
        
        // No password
        if (!password) {
            return { 
                score: 0, 
                label: 'Too weak', 
                className: 'is-danger',
                feedback: ['Password is required']
            };
        }
        
        // Length check (up to 40%)
        const lengthScore = Math.min(password.length * 4, 40);
        score += lengthScore;
        
        if (password.length < 8) {
            feedback.push('Password should be at least 8 characters');
        }
        
        // Character variety checks (up to 60%)
        const hasLower = /[a-z]/.test(password);
        const hasUpper = /[A-Z]/.test(password);
        const hasDigit = /\d/.test(password);
        const hasSpecial = /[^A-Za-z0-9]/.test(password);
        
        if (hasLower) score += 10;
        else feedback.push('Add lowercase letters');
        
        if (hasUpper) score += 15;
        else feedback.push('Add uppercase letters');
        
        if (hasDigit) score += 15;
        else feedback.push('Add numbers');
        
        if (hasSpecial) score += 20;
        else feedback.push('Add special characters');
        
        // Determine label and class based on score
        let label, className;
        if (score < 30) {
            label = 'Too weak';
            className = 'is-danger';
        } else if (score < 50) {
            label = 'Weak';
            className = 'is-warning';
        } else if (score < 80) {
            label = 'Good';
            className = 'is-info';
        } else {
            label = 'Strong';
            className = 'is-success';
        }
        
        return { score, label, className, feedback };
    }
    
    // Add some basic CSS for the strength meter
    const style = document.createElement('style');
    style.textContent = `
        .strength-meter {
            height: 5px;
            background-color: #e0e0e0;
            border-radius: 2px;
            margin-bottom: 5px;
        }
        .strength-meter-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.3s ease;
        }
        .strength-meter-fill.is-danger {
            background-color: #f14668;
        }
        .strength-meter-fill.is-warning {
            background-color: #ffdd57;
        }
        .strength-meter-fill.is-info {
            background-color: #3e8ed0;
        }
        .strength-meter-fill.is-success {
            background-color: #48c78e;
        }
    `;
    document.head.appendChild(style);
}); 