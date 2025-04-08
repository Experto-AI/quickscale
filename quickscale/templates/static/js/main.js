/* Main JavaScript file for QuickScale */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('QuickScale JavaScript initialized');
    
    // Set up mobile menu toggle if navbar-burger exists
    setupMobileMenu();
    
    // Set up flash message dismissal
    setupFlashMessages();
});

/**
 * Set up mobile menu toggle functionality
 */
function setupMobileMenu() {
    // Get all "navbar-burger" elements
    const $navbarBurgers = Array.prototype.slice.call(document.querySelectorAll('.navbar-burger'), 0);
    
    // Check if there are any navbar burgers
    if ($navbarBurgers.length > 0) {
        // Add a click event on each of them
        $navbarBurgers.forEach(el => {
            el.addEventListener('click', () => {
                // Get the target from the "data-target" attribute
                const target = el.dataset.target;
                const $target = document.getElementById(target);
                
                // Toggle the "is-active" class on both the "navbar-burger" and the "navbar-menu"
                el.classList.toggle('is-active');
                $target.classList.toggle('is-active');
            });
        });
    }
}

/**
 * Set up flash message dismissal functionality
 */
function setupFlashMessages() {
    // Get all message delete buttons
    const $deleteButtons = Array.prototype.slice.call(document.querySelectorAll('.message .delete'), 0);
    
    // Add click event to each delete button
    $deleteButtons.forEach(($delete) => {
        const $message = $delete.parentNode.parentNode;
        $delete.addEventListener('click', () => {
            $message.parentNode.removeChild($message);
        });
    });
}

/**
 * Utility function to create a cookie
 */
function setCookie(name, value, days) {
    let expires = "";
    if (days) {
        const date = new Date();
        date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
        expires = "; expires=" + date.toUTCString();
    }
    document.cookie = name + "=" + (value || "") + expires + "; path=/";
}

/**
 * Utility function to get a cookie value
 */
function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}
