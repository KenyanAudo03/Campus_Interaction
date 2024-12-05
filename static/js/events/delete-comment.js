// static/js/comments.js
function deleteComment(commentId) {
    if (!confirm('Are you sure you want to delete this comment?')) {
        return;
    }

    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;

    // Update the URL to match the Django URL pattern
    fetch(`/events/api/comments/${commentId}/delete/`, {  // Note the /events/ prefix
        method: 'DELETE',
        headers: {
            'X-CSRFToken': csrfToken,
            'Content-Type': 'application/json'
        },
    })
    .then(response => {
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Comment not found');
            }
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        // Remove the comment element from the DOM
        const commentElement = document.getElementById(`comment-${commentId}`);
        if (commentElement) {
            commentElement.remove();
            showNotification('Comment deleted successfully', 'success');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification(error.message || 'Failed to delete comment', 'error');
    });
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 2000);
}


