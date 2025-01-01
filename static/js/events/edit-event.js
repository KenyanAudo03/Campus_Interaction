document.addEventListener('DOMContentLoaded', function () {
                const editEventForm = document.getElementById('editEventForm');
                const saveEventChangesBtn = document.getElementById('saveEventChangesBtn');
            
                editEventForm.addEventListener('submit', function (event) {
                    event.preventDefault();
            
                    const eventId = document.getElementById('event-container').getAttribute('data-event-id');
                    const formData = new FormData(editEventForm);
                    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
            
                    fetch(`/api/events/${eventId}/update/`, {
                        method: 'PUT',
                        headers: {
                            'X-CSRFToken': csrfToken
                        },
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            alert(data.error);
                        } else {
                            // Handle successful update (e.g., close modal, show success message)
                            alert('Event updated successfully!');
                            // Reload the page or update the DOM as needed
                            location.reload();
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        alert('An error occurred while updating the event.');
                    });
                });
            });