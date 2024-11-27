document.addEventListener('DOMContentLoaded', function() {
    // Explicitly initialize modal
    if (document.getElementById('registrationModal')) {
        window.registrationModal = new bootstrap.Modal(document.getElementById('registrationModal'));
    }

    // Add explicit modal opening function
    window.openRegistrationModal = function() {
        if (window.registrationModal) {
            window.registrationModal.show();
        } else {
            console.error('Modal not initialized');
        }
    };
});
// event-registration.js
document.addEventListener('DOMContentLoaded', function() {
    const eventId = document.getElementById('event-container')?.dataset.eventId;
    if (!eventId) return;

    const registrationModal = new bootstrap.Modal(document.getElementById('registrationModal'));
    const form = document.getElementById('registrationForm');
    const alertsContainer = document.getElementById('registration-alerts');
    const statusContainer = document.getElementById('registration-status-container');
    const registerButton = document.getElementById('registerButton');
    function updateRegistrationButton(event) {
        if (!registerButton) return;
    
        const maxParticipants = event.max_participants;
        const spotsRemaining = event.spots_left;  // The API still returns as spots_left
    
        registerButton.disabled = false;
    
        if (maxParticipants === null || spotsRemaining > 0) {
            registerButton.classList.remove('btn-warning');
            registerButton.classList.add('btn-success');
            registerButton.innerHTML = '<i class="fas fa-user-plus"></i> Register for Event';
        } else {
            registerButton.classList.remove('btn-success');
            registerButton.classList.add('btn-warning');
            registerButton.innerHTML = '<i class="fas fa-user-plus"></i> Join Waiting List';
        }
    }
    
    // Add this function to your event-registration.js
function openRegistrationModal() {
    if (registrationModal) {
        registrationModal.show();
    }
}
    // Registration form submission
    document.getElementById('submitRegistration')?.addEventListener('click', handleRegistration);
    
    // Cancel registration
    document.getElementById('cancelRegistrationBtn')?.addEventListener('click', handleCancellation);

    // Periodic status check
    setInterval(() => checkEventStatus(), 30000); // Every 30 seconds
    
    async function handleRegistration(event) {
        event.preventDefault();
        clearAlerts();
        
        try {
            const formData = new FormData(form);
            const response = await fetch(`/events/event/${eventId}/register/`, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                showAlert('success', data.message);
                setTimeout(() => {
                    registrationModal.hide();
                    updateUI(data);
                }, 1500);
            } else {
                handleErrors(data.error);
            }
        } catch (error) {
            console.error('Registration error:', error);
            showAlert('danger', 'An unexpected error occurred. Please try again.');
        }
    }

    // More robust error handling
    function handleErrors(errors) {
        if (typeof errors === 'string') {
            showAlert('danger', errors);
            return;
        }
        
        // Handle both server-side and form validation errors
        Object.entries(errors).forEach(([field, messages]) => {
            const input = document.getElementById(`id_${field}`);
            const feedback = document.getElementById(`${field}-error`);
            if (input && feedback) {
                input.classList.add('is-invalid');
                feedback.textContent = Array.isArray(messages) ? messages.join(' ') : messages;
            }
        });
        
        // If no specific field errors, show a general error
        if (Object.keys(errors).length === 0) {
            showAlert('danger', 'Registration failed. Please check your details.');
        }
    }

   

    async function handleCancellation() {
        if (!confirm('Are you sure you want to cancel your registration?')) return;
        
        try {
            const response = await fetch(`/events/event/${eventId}/cancel/`, {
                method: 'POST',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                location.reload(); // Refresh to update UI
            } else {
                showAlert('danger', data.error || 'Failed to cancel registration');
            }
        } catch (error) {
            showAlert('danger', 'An error occurred while cancelling registration');
        }
    }
    
  
    async function checkEventStatus() {
        try {
            const response = await fetch(`/events/api/event/${eventId}/status/`);
            const data = await response.json();
            
            if (data.success) {
                updateStatusDisplay(data);
                updateRegistrationButton(data);
            }
        } catch (error) {
            console.error('Error checking event status:', error);
        }
    }
    
    function updateStatusDisplay(data) {
        const spotsCounter = document.getElementById('spots-counter');
        const waitlistCounter = document.getElementById('waitlist-counter');
        
        if (spotsCounter) {
            spotsCounter.textContent = data.spots_left === null ? 'Unlimited' : data.spots_left;
        }
        
        if (waitlistCounter) {
            waitlistCounter.textContent = `${data.waitlist_count} people`;
            waitlistCounter.parentElement.style.display = data.waitlist_count > 0 ? 'flex' : 'none';
        }
    }
    
    function updateUI(data) {
        // Update registration status
        if (statusContainer) {
            const statusHTML = `
                <div class="alert alert-success mb-3">
                    <i class="fas fa-check-circle"></i> 
                    ${data.status === 'registered' ? 
                      'You\'re registered!' : 
                      `You're on the waiting list (Position: ${data.waitlist_position})`}
                </div>
                <button type="button" 
                        class="btn btn-danger btn-lg w-100" 
                        id="cancelRegistrationBtn"
                        data-event-id="${eventId}">
                    <i class="fas fa-times"></i> Cancel Registration
                </button>
            `;
            statusContainer.innerHTML = statusHTML;
            
            // Reattach cancel event listener
            document.getElementById('cancelRegistrationBtn')?.addEventListener('click', handleCancellation);
        }
        
        // Update spots and waitlist info
        checkEventStatus();
    }
    
    function clearAlerts() {
        if (alertsContainer) alertsContainer.innerHTML = '';
        document.querySelectorAll('.invalid-feedback').forEach(el => el.textContent = '');
        document.querySelectorAll('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
    }
    
    function showAlert(type, message) {
        if (!alertsContainer) return;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.innerHTML = `<i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle"></i> ${message}`;
        alertsContainer.appendChild(alert);
    }
    
    function handleErrors(errors) {
        if (typeof errors === 'string') {
            showAlert('danger', errors);
            return;
        }
        
        for (const [field, messages] of Object.entries(errors)) {
            const input = document.getElementById(`id_${field}`);
            const feedback = document.getElementById(`${field}-error`);
            if (input && feedback) {
                input.classList.add('is-invalid');
                feedback.textContent = messages.join(' ');
            }
        }
    }
     // Attach event listener to form submission
    form.addEventListener('submit', handleRegistration);
});