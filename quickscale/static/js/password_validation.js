// This file is now empty as the Alpine.js code is placed directly in the templates
// The Alpine.js component is defined as a global function that templates can access
document.addEventListener('DOMContentLoaded', () => {
    window.passwordValidation = () => {
        return {
            password1: '',
            password2: '',
            score: 0,
            strength: '',
            feedback: '',
            color: '',
            passwordsMatch: false,
            
            init() {
                this.$watch('password1', () => {
                    this.checkPasswordStrength();
                    this.checkPasswordsMatch();
                });
                
                this.$watch('password2', () => {
                    this.checkPasswordsMatch();
                });
            },
            
            checkPasswordStrength() {
                // Initialize score
                this.score = 0;
                
                // Return early if password is empty
                if (this.password1.length === 0) {
                    this.strength = '';
                    this.feedback = '';
                    this.color = '';
                    return;
                }
                
                // Length check
                if (this.password1.length >= 8) {
                    this.score += 1;
                }
                if (this.password1.length >= 12) {
                    this.score += 1;
                }
                
                // Complexity checks
                if (/[A-Z]/.test(this.password1)) this.score += 1; // Has uppercase
                if (/[a-z]/.test(this.password1)) this.score += 1; // Has lowercase
                if (/[0-9]/.test(this.password1)) this.score += 1; // Has number
                if (/[^A-Za-z0-9]/.test(this.password1)) this.score += 1; // Has special character
                
                // Determine strength based on score
                this.strength = 'weak';
                this.feedback = 'Password is too weak';
                this.color = 'is-danger';
                
                if (this.score >= 4) {
                    this.strength = 'medium';
                    this.feedback = 'Password strength: Medium';
                    this.color = 'is-warning';
                }
                if (this.score >= 6) {
                    this.strength = 'strong';
                    this.feedback = 'Password strength: Strong';
                    this.color = 'is-success';
                }
            },
            
            checkPasswordsMatch() {
                if (this.password2.length === 0) {
                    this.passwordsMatch = false;
                    return;
                }
                
                this.passwordsMatch = (this.password1 === this.password2);
            },
            
            // Properties for the UI
            progressValue() {
                return this.score;
            },
            
            isSubmitDisabled() {
                return (this.score < 4 || (this.password2.length > 0 && !this.passwordsMatch));
            },
            
            matchMessage() {
                if (this.password2.length === 0) {
                    return '';
                }
                
                return this.passwordsMatch ? 
                    'Passwords match' : 
                    'Passwords do not match';
            },
            
            matchMessageClass() {
                return this.passwordsMatch ? 'is-success' : 'is-danger';
            }
        };
    };
}); 