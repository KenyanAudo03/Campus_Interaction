function getCsrfToken() {
    return document.querySelector("[name=csrfmiddlewaretoken]").value;
}

function toggleLike(postId, button) {
    fetch(`/feeds/post/${postId}/like/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
        },
    })
        .then((response) => response.json())
        .then((data) => {
            const likesCount = button.querySelector(".likes-count");
            likesCount.textContent = data.likes_count;
            button.classList.toggle("liked", data.is_liked);
        })
        .catch((error) => console.error("Error:", error));
}

function deletePost(postId) {
    Swal.fire({
        title: 'Delete Post?',
        text: "This action cannot be undone.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Yes, delete it'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/feeds/post/${postId}/delete/`, {
                method: "POST",
                headers: {
                    "X-CSRFToken": getCsrfToken(),
                },
            })
            .then((response) => {
                if (response.ok) {
                    const postElement = document.querySelector(`#post-${postId}`);
                    postElement.remove();
                    Swal.fire('Deleted!', 'Your post has been deleted.', 'success');
                } else {
                    throw new Error('Failed to delete post');
                }
            })
            .catch((error) => {
                console.error("Error:", error);
                Swal.fire('Error!', 'Failed to delete post.', 'error');
            });
        }
    });
}

function loadPostDetail(postId, event) {
    event.stopPropagation();
    
    if (event.target.tagName === 'VIDEO' || 
        event.target.tagName === 'A' || 
        event.target.closest('.engagement-btn')) {
        return;
    }
    
    window.location.href = `/feeds/post/${postId}/`;
} 