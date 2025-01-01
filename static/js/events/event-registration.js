document.addEventListener('DOMContentLoaded', function() {
    const config = {
        selectors: {
            eventContainer: '#event-container',
            registrationModal: '#registrationModal',
            registrationForm: '#registrationForm',
            alertsContainer: '#registration-alerts',
            statusContainer: '#registration-status-container',
            registerButton: '#registerButton',
            submitRegistrationBtn: '#submitRegistration',
            cancelRegistrationBtn: '#cancelRegistrationBtn'
        },
        urls: {
            base: '/events',
            register: (eventId) => `/events/event/${eventId}/register/`,
            cancel: (eventId) => `/events/event/${eventId}/cancel/`,
            status: (eventId) => `/events/api/event/${eventId}/status/`,
            waitlist: (eventId) => `/events/event/${eventId}/waitlist/`,
            redirect: '/events/'
        },
        retryConfig: {
            maxRetries: 3,
            baseDelay: 1000
        }
    };

    const trustedUrls = [
        'https://trustedsite.com/',
        'https://anothertrustedsite.com/',
        '/about/',
        '/contact/'
    ];

    const utils = {
        getElement: (selector) => document.querySelector(selector),
        getElements: (selector) => document.querySelectorAll(selector),
        
        showAlert: (type, message) => {
            const alertsContainer = utils.getElement(config.selectors.alertsContainer);
            if (!alertsContainer) return;
            
            alertsContainer.innerHTML = `
                <div class="alert alert-${type} alert-dismissible fade show" role="alert">
                    <i class="fas fa-${type === 'success' ? 'check' : 'exclamation'}-circle me-2"></i> 
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        },

        clearFormErrors: () => {
            utils.getElements('.is-invalid').forEach(el => el.classList.remove('is-invalid'));
            utils.getElements('.invalid-feedback').forEach(el => el.textContent = '');
        },

        getCsrfToken: () => {
            const token = document.querySelector('[name=csrfmiddlewaretoken]');
            if (!token) {
                throw new Error('CSRF token not found');
            }
            return token.value;
        },

        isTrustedUrl: (url) => {
            try {
                const parsedUrl = new URL(url, window.location.origin);
                return trustedUrls.some(trusted => parsedUrl.href.startsWith(new URL(trusted, window.location.origin).href));
            } catch (e) {
                return false;
            }
        },

        redirectTo: (url) => {
            if (utils.isTrustedUrl(url)) {
                window.location.href = url;
            } else {
                console.error('Attempted redirection to untrusted URL:', url);
            }
        }
    };

    // Event Registration Handler
    class EventRegistration {
        constructor() {
            this.eventId = this.getEventId();
            this.registrationModal = new bootstrap.Modal(utils.getElement(config.selectors.registrationModal));
            this.init();
        }

        getEventId() {
            const eventContainer = utils.getElement(config.selectors.eventContainer);
            if (!eventContainer) {
                console.error('Event container not found');
                return null;
            }
            const eventId = eventContainer.dataset.eventId;
            if (!eventId) {
                console.error('Event ID is missing');
                return null;
            }
            return eventId;
        }

        init() {
            this.bindEvents();
            this.checkEventStatus();
            // Periodic status check
            setInterval(() => this.checkEventStatus(), 50000);
        }

        bindEvents() {
            const form = utils.getElement(config.selectors.registrationForm);
            const submitBtn = utils.getElement(config.selectors.submitRegistrationBtn);
            const cancelBtn = utils.getElement(config.selectors.cancelRegistrationBtn);
            const registerButton = utils.getElement(config.selectors.registerButton);

            if (form) form.addEventListener('submit', (e) => this.handleRegistration(e));
            if (submitBtn) submitBtn.addEventListener('click', (e) => this.handleRegistration(e));
            if (cancelBtn) cancelBtn.addEventListener('click', () => this.handleCancellation());
            if (registerButton) registerButton.addEventListener('click', (e) => this.handleRegisterOrWaitlist(e));
        }

        async handleRegisterOrWaitlist(event) {
            const action = event.target.dataset.action;
            if (action === 'register') {
                this.handleRegistration(event);
            } else if (action === 'waitlist') {
                this.handleWaitlist(event);
            }
        }

        async handleRegistration(event) {
            event.preventDefault();
            utils.clearFormErrors();

            const form = utils.getElement(config.selectors.registrationForm);
            const formData = new FormData(form);

            try {
                const response = await this.fetchWithRetry(
                    config.urls.register(this.eventId), 
                    {
                        method: 'POST',
                        body: formData,
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': utils.getCsrfToken()
                        }
                    }
                );

                if (response.success) {
                    utils.showAlert('success', response.message);
                    setTimeout(() => {
                        this.registrationModal.hide();
                        this.updateRegistrationButton(response);
                    }, 1500);
                } else {
                    this.handleErrors(response.errors || response.error);
                }
            } catch (error) {
                console.error('Registration error:', error);
                utils.showAlert('danger', 'An unexpected error occurred. Please try again.');
            }
        }

        async handleWaitlist(event) {
            event.preventDefault();
            utils.clearFormErrors();

            try {
                const response = await this.fetchWithRetry(
                    config.urls.waitlist(this.eventId), 
                    {
                        method: 'POST',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': utils.getCsrfToken()
                        }
                    }
                );

                if (response.success) {
                    utils.showAlert('success', response.message);
                    this.updateRegistrationButton(response);
                } else {
                    this.handleErrors(response.errors || response.error);
                }
            } catch (error) {
                console.error('Waitlist error:', error);
                utils.showAlert('danger', 'An unexpected error occurred. Please try again.');
            }
        }

        async handleCancellation() {
            if (!confirm('Are you sure you want to cancel your registration?')) return;
        
            try {
                const response = await this.fetchWithRetry(
                    config.urls.cancel(this.eventId), 
                    {
                        method: 'POST',
                        credentials: 'include',
                        headers: {
                            'X-Requested-With': 'XMLHttpRequest',
                            'X-CSRFToken': utils.getCsrfToken()
                        }
                    }
                );
        
                if (response.success) {
                    const statusContainer = utils.getElement(config.selectors.statusContainer);
                    if (statusContainer) statusContainer.innerHTML = '';
        
                    // Update UI based on additional context
                    if (response.waitlist_promoted) {
                        utils.showAlert('info', 'A waiting list participant has been promoted to the event.');
                    }
        
                    await this.checkEventStatus();
                    
                    utils.showAlert('success', response.message || 'Registration cancelled successfully');
                    setTimeout(() => {
                        this.updateRegistrationButton(response);
                    }, 1500);
                } else {
                    // Enhanced error handling
                    let errorMessage = response.error || 'Failed to cancel registration';
                    
                    // Log additional details for debugging
                    console.error('Cancellation Failed:', {
                        eventId: this.eventId,
                        errorDetails: response.details,
                        timestamp: new Date().toISOString()
                    });
                    // Provide more context in the error message
                    if (response.details) {
                        errorMessage += `. Total registrations: ${response.details.total_registrations}`;
                        errorMessage += `. Statuses: ${response.details.registration_statuses.join(', ')}`;
                    }
        
                    utils.showAlert('danger', errorMessage);
                }
            } catch (error) {
                utils.showAlert('danger', 'An unexpected error occurred while cancelling registration');
                console.error('Cancellation error:', error);
            }
        }

        async fetchWithRetry(url, options, retryCount = 0) {
            try {
                const response = await fetch(url, options);
                const data = await response.json();

                if (!data.success && data.error && data.error.includes('currently being processed')) {
                    if (retryCount < config.retryConfig.maxRetries) {
                        await new Promise(resolve => setTimeout(resolve, config.retryConfig.baseDelay * (retryCount + 1)));
                        return this.fetchWithRetry(url, options, retryCount + 1);
                    }
                }

                return data;
            } catch (error) {
                if (retryCount < config.retryConfig.maxRetries) {
                    await new Promise(resolve => setTimeout(resolve, config.retryConfig.baseDelay * (retryCount + 1)));
                    return this.fetchWithRetry(url, options, retryCount + 1);
                }
                throw error;
            }
        }

        async checkEventStatus() {
            try {
                const response = await fetch(config.urls.status(this.eventId));
                const data = await response.json();
                
                if (data.success) {
                    this.updateRegistrationButton({
                        max_participants: data.total_spots || null,
                        spots_left: data.spots_left || null,
                        userStatus: {
                            is_registered: data.user_status?.is_registered || false,
                            status: data.user_status?.status || null
                        }
                    });
                }
            } catch (error) {
                console.error('Error checking event status:', error);
            }
        }

        updateRegistrationButton(event) {
            const registerButton = utils.getElement(config.selectors.registerButton);
            if (!registerButton) return;
        
            // Destructure event details with comprehensive defaults
            const {
                max_participants = null,
                spots_left = 0,
                userStatus = { 
                    is_registered: false, 
                    status: null 
                },
                event_start_date = null,
                registration_open = true,
                is_waitlist_open = true,
                waitlist_count = 0
            } = event;
        
            // Comprehensive button states configuration
            const buttonStates = {
                // Registered states
                registered: {
                    class: 'btn-danger',
                    icon: 'times',
                    text: 'Cancel Registration',
                    modal: false,
                    action: 'cancel'
                },
                waitlist: {
                    class: 'btn-warning',
                    icon: 'clock',
                    text: `On Waiting List (Position: ${userStatus.waitlist_position || 'N/A'})`,
                    modal: false,
                    action: 'cancel'
                },
                
                // Available states
                available: {
                    class: 'btn-success',
                    icon: 'user-plus',
                    text: 'Register for Event',
                    modal: true,
                    action: 'register'
                },
                
                // Full event states
                full_waitlist: {
                    class: 'btn-warning',
                    icon: 'list',
                    text: `Join Waiting List (${waitlist_count} people)`,
                    modal: true,
                    action: 'waitlist'
                },
                full_no_waitlist: {
                    class: 'btn-secondary',
                    icon: 'ban',
                    text: 'Event Full',
                    modal: false,
                    action: 'none'
                },
                
                // Closed states
                closed: {
                    class: 'btn-secondary',
                    icon: 'ban',
                    text: 'Registration Closed',
                    modal: false,
                    action: 'none'
                },
                past: {
                    class: 'btn-secondary',
                    icon: 'calendar-times',
                    text: 'Event Passed',
                    modal: false,
                    action: 'none'
                }
            };
        
            // Determine button state logic
            const determineButtonState = () => {
                // Event has passed
                if (event_start_date && new Date(event_start_date) < new Date()) {
                    return 'past';
                }
        
                // Registration not open
                if (!registration_open) {
                    return 'closed';
                }
        
                // User is already registered
                if (userStatus.is_registered) {
                    return userStatus.status === 'registered' ? 'registered' : 'waitlist';
                }
        
                // Event has unlimited spots or has available spots
                if (max_participants === null || spots_left > 0) {
                    return 'available';
                }
        
                // Event is full
                return 'full';
            };
        
            // Get the current state
            const currentState = determineButtonState();
            const buttonConfig = buttonStates[currentState];
        
            // Reset button classes and attributes
            registerButton.className = `btn ${buttonConfig.class} btn-lg w-100`;
            registerButton.innerHTML = `
                <i class="fas fa-${buttonConfig.icon}"></i> 
                ${buttonConfig.text}
            `;
        
            // Configure modal and click behavior
            if (buttonConfig.modal) {
                registerButton.setAttribute('data-bs-toggle', 'modal');
                registerButton.setAttribute('data-bs-target', '#registrationModal');
            } else {
                registerButton.removeAttribute('data-bs-toggle');
                registerButton.removeAttribute('data-bs-target');
            }
        
            // Disable button for non-interactive states
            registerButton.disabled = buttonConfig.action === 'none';
        
            // Optional: Add tooltips or additional context
            if (currentState === 'full_waitlist') {
                registerButton.setAttribute('title', `Waiting list has ${waitlist_count} people`);
            } else if (currentState === 'past') {
                registerButton.setAttribute('title', 'This event has already occurred');
            }
        
            // Add data attributes for tracking
            registerButton.dataset.eventState = currentState;
            registerButton.dataset.action = buttonConfig.action;
            registerButton.dataset.spotsLeft = spots_left || 0;
            registerButton.dataset.maxParticipants = max_participants || 0;

            // Reattach event listeners
            this.bindEvents();
        }

        handleErrors(errors) {
            if (typeof errors === 'string') {
                utils.showAlert('danger', errors);
                return;
            }
            
            Object.entries(errors).forEach(([field, messages]) => {
                const input = document.getElementById(`id_${field}`);
                const feedback = document.getElementById(`${field}-error`);
                
                if (input && feedback) {
                    input.classList.add('is-invalid');
                    feedback.textContent = Array.isArray(messages) ? messages.join(' ') : messages;
                }
            });
            
            if (Object.keys(errors).length === 0) {
                utils.showAlert('danger', 'Registration failed. Please check your details.');
            }
        }
    }

    // Initialize Event Registration
    new EventRegistration();

    // Expose function to open registration modal globally
    window.openRegistrationModal = function() {
        const registrationModal = utils.getElement(config.selectors.registrationModal);
        if (registrationModal) {
            new bootstrap.Modal(registrationModal).show();
        }
    };
});