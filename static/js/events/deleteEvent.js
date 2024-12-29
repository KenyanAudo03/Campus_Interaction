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
            button.addEventListener('click', function(e) {
                e.preventDefault();
                
                const eventId = this.getAttribute('data-event-id');
                const modal = new bootstrap.Modal(document.getElementById('deleteEventModal'));

                // Store event ID in a data attribute on the modal confirm button
                document.getElementById('confirmDeleteBtn').setAttribute('data-event-id', eventId);

                modal.show();
            });
        });

        // Handle the modal confirmation button click
        document.getElementById('confirmDeleteBtn').addEventListener('click', async function() {
            const eventId = this.getAttribute('data-event-id');
            await handleDeleteEvent(eventId);
            
            // Close the modal after the event is handled
            const modalInstance = bootstrap.Modal.getInstance(document.getElementById('deleteEventModal'));
            modalInstance.hide();
        });
    });
}

// Handle event deletion
async function handleDeleteEvent(eventId) {
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
            showNotification('Event deleted successfully', 'success');
            setTimeout(() => {
                window.location.href = '/events/';
            }, 1500);
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
    }, 500);
}
