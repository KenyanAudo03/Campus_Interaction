// First, check if we've already initialized to prevent multiple attachments
if (!window.eventListenersInitialized) {
    window.eventListenersInitialized = true;
    
    document.addEventListener('DOMContentLoaded', function() {
        // Remove any existing event listeners
        document.querySelectorAll('.delete-event-btn').forEach(button => {
            button.replaceWith(button.cloneNode(true));
        });
        
        // Add new event listeners
        document.querySelectorAll('.delete-event-btn').forEach(button => {
            button.addEventListener('click', handleDeleteEvent);
        });
    });
}

// Separate the handler function for clarity
async function handleDeleteEvent(e) {
    e.preventDefault();
    
    if (!confirm('Are you sure you want to delete this event?')) {
        return;
    }

    const eventId = this.getAttribute('data-event-id');
    
    try {
        const response = await fetch(`/events/${eventId}/delete/`, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': getCsrfToken(),
                'Content-Type': 'application/json',
            },
            credentials: 'same-origin'
        });

        const data = await response.json();

        if (response.ok) {
            console.log("Redirecting to event list...");
            window.location.href = '/events/';
        } else {
            showNotification(data.message || 'Failed to delete event', 'error');
        }
        
    } catch (error) {
        console.error('Error:', error);
        showNotification('Error deleting event', 'error');
    }
}

// Helper functions remain the same
function getCsrfToken() {
    return document.querySelector('[name=csrfmiddlewaretoken]').value;
}

function showNotification(message, type) {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show`;
    alertDiv.role = 'alert';
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
    `;
    document.querySelector('#notifications-container').appendChild(alertDiv);
    
    setTimeout(() => {
        alertDiv.remove();
    }, 2000);
}