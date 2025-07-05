/**
 * QuickScale Password Validation - Pure Alpine.js Implementation
 * 
 * This file provides Alpine.js data functions for password validation.
 * All DOM interactions should be handled via Alpine.js directives in templates.
 * Updated to use 8-character minimum requirement.
 */

// Alpine.js data function for password validation
document.addEventListener('alpine:init', () => {
    Alpine.data('passwordValidation', () => ({
        password1: '',
        password2: '',
        
        // Calculate password strength score
        progressValue() {
            let score = 0;
            const password = this.password1;
            
            // Updated to match server-side 8-character minimum
            if (password.length >= 8) score++;
            if (password.match(/[a-z]/) && password.match(/[A-Z]/)) score++;
            if (password.match(/\d/)) score++;
            if (password.match(/[^a-zA-Z\d]/)) score++;
            if (password.length >= 12) score++;
            if (password.length >= 16) score++;
            
            return score;
        },
        
        // Get progress bar color class
        get color() {
            const score = this.progressValue();
            if (score <= 2) return 'is-danger';
            if (score <= 4) return 'is-warning';
            return 'is-success';
        },
        
        // Get password strength feedback
        get feedback() {
            const score = this.progressValue();
            const password = this.password1;
            
            // Provide specific feedback based on requirements
            if (password.length === 0) return 'Enter a password';
            if (password.length < 8) return `Password must be at least 8 characters (${password.length}/8)`;
            if (!password.match(/[a-z]/)) return 'Password must contain lowercase letters';
            if (!password.match(/[A-Z]/)) return 'Password must contain uppercase letters';
            if (!password.match(/\d/)) return 'Password must contain numbers';
            if (!password.match(/[^a-zA-Z\d]/)) return 'Password must contain special characters';
            
            if (score <= 2) return 'Weak password - consider adding more complexity';
            if (score <= 4) return 'Good password - meets requirements';
            return 'Strong password - excellent security';
        },
        
        // Get password match message
        matchMessage() {
            if (!this.password2) return '';
            return this.password1 === this.password2 ? 'Passwords match' : 'Passwords do not match';
        },
        
        // Get password match message CSS class
        matchMessageClass() {
            if (!this.password2) return '';
            return this.password1 === this.password2 ? 'is-success' : 'is-danger';
        },
        
        // Check if submit should be disabled
        isSubmitDisabled() {
            // Ensure password meets minimum requirements and passwords match
            return this.password1 !== this.password2 || 
                   this.password1.length < 8 || 
                   !this.password1.match(/[a-z]/) ||
                   !this.password1.match(/[A-Z]/) ||
                   !this.password1.match(/\d/) ||
                   !this.password1.match(/[^a-zA-Z\d]/);
        },
        
        // Get password requirements with status
        getPasswordRequirements() {
            const password = this.password1;
            return [
                { text: 'At least 8 characters', met: password.length >= 8 },
                { text: 'Contains lowercase letters', met: !!password.match(/[a-z]/) },
                { text: 'Contains uppercase letters', met: !!password.match(/[A-Z]/) },
                { text: 'Contains numbers', met: !!password.match(/\d/) },
                { text: 'Contains special characters', met: !!password.match(/[^a-zA-Z\d]/) }
            ];
        },
        
        // Get progress bar width percentage
        get progressWidth() {
            const score = this.progressValue();
            return Math.min(score * 16.67, 100); // 6 possible points * 16.67 = 100%
        }
    }));
});

// Advanced password validation component for complex forms
document.addEventListener('alpine:init', () => {
    Alpine.data('advancedPasswordValidation', () => ({
        password1: '',
        password2: '',
        showRequirements: false,
        
        // Toggle requirements visibility
        toggleRequirements() {
            this.showRequirements = !this.showRequirements;
        },
        
        // Get detailed password analysis
        getPasswordAnalysis() {
            const password = this.password1;
            const analysis = {
                length: password.length,
                hasLowercase: /[a-z]/.test(password),
                hasUppercase: /[A-Z]/.test(password),
                hasDigit: /\d/.test(password),
                hasSpecial: /[^a-zA-Z\d]/.test(password),
                score: 0
            };
            
            // Calculate score
            if (analysis.length >= 8) analysis.score += 20;
            if (analysis.hasLowercase) analysis.score += 20;
            if (analysis.hasUppercase) analysis.score += 20;
            if (analysis.hasDigit) analysis.score += 20;
            if (analysis.hasSpecial) analysis.score += 20;
            
            return analysis;
        },
        
        // Get strength level text
        get strengthLevel() {
            const analysis = this.getPasswordAnalysis();
            if (analysis.score >= 100) return 'Strong';
            if (analysis.score >= 80) return 'Good';
            if (analysis.score >= 60) return 'Fair';
            if (analysis.score >= 40) return 'Weak';
            return 'Very Weak';
        },
        
        // Check if form is valid for submission
        get isFormValid() {
            const analysis = this.getPasswordAnalysis();
            return analysis.score === 100 && this.password1 === this.password2;
        }
    }));
});

// Utility function for HTMX password validation if needed
function validatePasswordForHTMX(password) {
    const requirements = {
        length: password.length >= 8,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        digit: /[0-9]/.test(password),
        special: /[^A-Za-z0-9]/.test(password)
    };
    
    let score = 0;
    Object.values(requirements).forEach(met => {
        if (met) score += 20;
    });
    
    let strengthClass = 'is-danger';
    let strengthText = 'Weak password - missing requirements';
    
    if (score === 100) {
        strengthClass = 'is-success';
        strengthText = 'Strong password - all requirements met';
    } else if (score >= 60) {
        strengthClass = 'is-warning';
        strengthText = 'Good password - almost there';
    }
    
    return { 
        score, 
        strengthClass, 
        strengthText, 
        width: `${score}%`, 
        requirements 
    };
} 