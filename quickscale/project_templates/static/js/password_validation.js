/**
 * QuickScale Password Validation - Modular Alpine.js Implementation
 * 
 * This file provides reusable Alpine.js components for password validation.
 * All DOM interactions should be handled via Alpine.js directives in templates.
 * Updated to use 8-character minimum requirement with modular design.
 */

// Shared password validation utilities
const PasswordUtils = {
    // Validation patterns
    patterns: {
        lowercase: /[a-z]/,
        uppercase: /[A-Z]/,
        digit: /\d/,
        special: /[^a-zA-Z\d]/,
        minLength: 8
    },
    
    // Check if password meets a specific requirement
    meetsRequirement(password, requirement) {
        switch (requirement) {
            case 'length':
                return password.length >= this.patterns.minLength;
            case 'lowercase':
                return this.patterns.lowercase.test(password);
            case 'uppercase':
                return this.patterns.uppercase.test(password);
            case 'digit':
                return this.patterns.digit.test(password);
            case 'special':
                return this.patterns.special.test(password);
            default:
                return false;
        }
    },
    
    // Calculate password strength score (0-100)
    calculateStrengthScore(password) {
        if (!password) return 0;
        
        const requirements = ['length', 'lowercase', 'uppercase', 'digit', 'special'];
        const metCount = requirements.filter(req => this.meetsRequirement(password, req)).length;
        const baseScore = (metCount / requirements.length) * 80;
        
        // Bonus points for longer passwords
        const lengthBonus = Math.min(password.length - this.patterns.minLength, 8) * 2.5;
        
        return Math.min(baseScore + lengthBonus, 100);
    },
    
    // Get strength level description
    getStrengthLevel(score) {
        if (score >= 90) return { text: 'Excellent', class: 'is-success', color: '#48c774' };
        if (score >= 70) return { text: 'Strong', class: 'is-success', color: '#48c774' };
        if (score >= 50) return { text: 'Good', class: 'is-warning', color: '#ffdd57' };
        if (score >= 25) return { text: 'Weak', class: 'is-danger', color: '#f14668' };
        return { text: 'Very Weak', class: 'is-danger', color: '#f14668' };
    },
    
    // Calculate password entropy
    calculateEntropy(password) {
        if (!password) return 0;
        
        let charSetSize = 0;
        if (this.patterns.lowercase.test(password)) charSetSize += 26;
        if (this.patterns.uppercase.test(password)) charSetSize += 26;
        if (this.patterns.digit.test(password)) charSetSize += 10;
        if (this.patterns.special.test(password)) charSetSize += 32;
        
        return password.length * Math.log2(charSetSize || 1);
    },
    
    // Check for common patterns
    hasCommonPatterns(password) {
        const commonPatterns = [
            'password', 'admin', 'user', 'login', 'welcome', 'qwerty',
            '123456', 'abc123', 'letmein', 'monkey', 'password123'
        ];
        
        const lowerPassword = password.toLowerCase();
        return commonPatterns.some(pattern => lowerPassword.includes(pattern));
    }
};

// Base password validation component
document.addEventListener('alpine:init', () => {
    Alpine.data('passwordValidator', (options = {}) => ({
        password1: '',
        password2: '',
        showRequirements: options.showRequirements || false,
        showAnalysis: options.showAnalysis || false,
        
        // Get password requirements with status
        get requirements() {
            const password = this.password1;
            return [
                {
                    id: 'length',
                    text: 'At least 8 characters',
                    met: PasswordUtils.meetsRequirement(password, 'length'),
                    detail: `Current: ${password.length} characters`
                },
                {
                    id: 'lowercase',
                    text: 'Contains lowercase letters (a-z)',
                    met: PasswordUtils.meetsRequirement(password, 'lowercase'),
                    detail: PasswordUtils.meetsRequirement(password, 'lowercase') ? 'Lowercase found' : 'Missing lowercase letters'
                },
                {
                    id: 'uppercase',
                    text: 'Contains uppercase letters (A-Z)',
                    met: PasswordUtils.meetsRequirement(password, 'uppercase'),
                    detail: PasswordUtils.meetsRequirement(password, 'uppercase') ? 'Uppercase found' : 'Missing uppercase letters'
                },
                {
                    id: 'digit',
                    text: 'Contains numbers (0-9)',
                    met: PasswordUtils.meetsRequirement(password, 'digit'),
                    detail: PasswordUtils.meetsRequirement(password, 'digit') ? 'Numbers found' : 'Missing numbers'
                },
                {
                    id: 'special',
                    text: 'Contains special characters (!@#$%^&*)',
                    met: PasswordUtils.meetsRequirement(password, 'special'),
                    detail: PasswordUtils.meetsRequirement(password, 'special') ? 'Special characters found' : 'Missing special characters'
                }
            ].map(req => ({
                ...req,
                icon: req.met ? '✓' : '✗',
                class: req.met ? 'has-text-success' : 'has-text-danger'
            }));
        },
        
        // Get password strength information
        get strength() {
            const score = PasswordUtils.calculateStrengthScore(this.password1);
            const level = PasswordUtils.getStrengthLevel(score);
            
            return {
                score,
                level,
                progressWidth: score,
                progressClass: level.class
            };
        },
        
        // Get password match status
        get passwordMatch() {
            if (!this.password2) return { status: 'none', message: '', class: '' };
            
            const match = this.password1 === this.password2;
            return {
                status: match ? 'match' : 'mismatch',
                message: match ? '✓ Passwords match' : '✗ Passwords do not match',
                class: match ? 'has-text-success' : 'has-text-danger'
            };
        },
        
        // Check if form is valid for submission
        get isValid() {
            const allRequirementsMet = this.requirements.every(req => req.met);
            const passwordsMatch = this.password1 === this.password2;
            return allRequirementsMet && passwordsMatch;
        },
        
        // Get user-friendly feedback
        get feedback() {
            const password = this.password1;
            
            if (password.length === 0) return 'Enter a password';
            
            const unmetRequirements = this.requirements.filter(req => !req.met);
            if (unmetRequirements.length > 0) {
                return unmetRequirements[0].detail;
            }
            
            const level = this.strength.level;
            return `${level.text} password - ${level.text === 'Excellent' ? 'excellent security' : 'meets requirements'}`;
        },
        
        // Toggle requirements visibility
        toggleRequirements() {
            this.showRequirements = !this.showRequirements;
        },
        
        // Toggle analysis visibility
        toggleAnalysis() {
            this.showAnalysis = !this.showAnalysis;
        }
    }));
});

// Enhanced password validation component with detailed analysis
document.addEventListener('alpine:init', () => {
    Alpine.data('enhancedPasswordValidator', (options = {}) => ({
        ...Alpine.raw(Alpine.data('passwordValidator')(options)),
        
        // Get detailed password analysis
        get analysis() {
            const password = this.password1;
            const charTypes = {
                lowercase: (password.match(/[a-z]/g) || []).length,
                uppercase: (password.match(/[A-Z]/g) || []).length,
                numbers: (password.match(/\d/g) || []).length,
                special: (password.match(/[^a-zA-Z\d]/g) || []).length,
                unique: new Set(password).size
            };
            
            const entropy = PasswordUtils.calculateEntropy(password);
            const hasCommonPatterns = PasswordUtils.hasCommonPatterns(password);
            
            return {
                length: password.length,
                charTypes,
                entropy: Math.round(entropy),
                uniqueChars: charTypes.unique,
                hasCommonPatterns,
                strengthScore: this.strength.score
            };
        },
        
        // Get suggestions for improving password
        get suggestions() {
            const suggestions = [];
            const unmetRequirements = this.requirements.filter(req => !req.met);
            
            unmetRequirements.forEach(req => {
                switch (req.id) {
                    case 'length':
                        suggestions.push('Make your password longer (at least 8 characters)');
                        break;
                    case 'lowercase':
                        suggestions.push('Add lowercase letters (a-z)');
                        break;
                    case 'uppercase':
                        suggestions.push('Add uppercase letters (A-Z)');
                        break;
                    case 'digit':
                        suggestions.push('Add numbers (0-9)');
                        break;
                    case 'special':
                        suggestions.push('Add special characters (!@#$%^&*)');
                        break;
                }
            });
            
            if (this.analysis.hasCommonPatterns) {
                suggestions.push('Avoid common words or patterns');
            }
            
            if (this.analysis.uniqueChars < this.password1.length * 0.7) {
                suggestions.push('Use more unique characters');
            }
            
            return suggestions;
        }
    }));
});

// Simple password validation component for basic forms
document.addEventListener('alpine:init', () => {
    Alpine.data('simplePasswordValidator', () => ({
        password: '',
        
        get isValid() {
            return PasswordUtils.calculateStrengthScore(this.password) >= 80;
        },
        
        get strength() {
            const score = PasswordUtils.calculateStrengthScore(this.password);
            const level = PasswordUtils.getStrengthLevel(score);
            return {
                score,
                level,
                progressWidth: score,
                progressClass: level.class
            };
        },
        
        get feedback() {
            if (!this.password) return 'Enter a password';
            
            const requirements = ['length', 'lowercase', 'uppercase', 'digit', 'special'];
            const unmetRequirement = requirements.find(req => !PasswordUtils.meetsRequirement(this.password, req));
            
            if (unmetRequirement) {
                const messages = {
                    length: 'Password must be at least 8 characters',
                    lowercase: 'Password must contain lowercase letters',
                    uppercase: 'Password must contain uppercase letters',
                    digit: 'Password must contain numbers',
                    special: 'Password must contain special characters'
                };
                return messages[unmetRequirement];
            }
            
            return `${this.strength.level.text} password`;
        }
    }));
});

// Backward compatibility utility function for HTMX integration
function validatePasswordForHTMX(password) {
    const score = PasswordUtils.calculateStrengthScore(password);
    const level = PasswordUtils.getStrengthLevel(score);
    
    const requirements = {
        length: PasswordUtils.meetsRequirement(password, 'length'),
        uppercase: PasswordUtils.meetsRequirement(password, 'uppercase'),
        lowercase: PasswordUtils.meetsRequirement(password, 'lowercase'),
        digit: PasswordUtils.meetsRequirement(password, 'digit'),
        special: PasswordUtils.meetsRequirement(password, 'special')
    };
    
    return { 
        score, 
        strengthClass: level.class,
        strengthText: `${level.text} password`,
        width: `${score}%`, 
        requirements 
    };
}

// Export for use in other modules if needed
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { PasswordUtils, validatePasswordForHTMX };
} 