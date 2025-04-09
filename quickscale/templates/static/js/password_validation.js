// Password validation functionality using Alpine.js

document.addEventListener('alpine:init', () => {
    Alpine.data('passwordValidation', () => ({
        password1: '',
        password2: '',
        progressValue() {
            let score = 0;
            const password = this.password1;
            
            if (password.length >= 8) score++;
            if (password.match(/[a-z]/) && password.match(/[A-Z]/)) score++;
            if (password.match(/\d/)) score++;
            if (password.match(/[^a-zA-Z\d]/)) score++;
            if (password.length >= 12) score++;
            if (password.length >= 16) score++;
            
            return score;
        },
        get color() {
            const score = this.progressValue();
            if (score <= 2) return 'is-danger';
            if (score <= 4) return 'is-warning';
            return 'is-success';
        },
        get feedback() {
            const score = this.progressValue();
            if (score <= 2) return 'Weak password';
            if (score <= 4) return 'Good password';
            return 'Strong password';
        },
        matchMessage() {
            if (!this.password2) return '';
            return this.password1 === this.password2 ? 'Passwords match' : 'Passwords do not match';
        },
        matchMessageClass() {
            if (!this.password2) return '';
            return this.password1 === this.password2 ? 'is-success' : 'is-danger';
        },
        isSubmitDisabled() {
            return this.password1 !== this.password2 || this.progressValue() < 3;
        }
    }));
}); 