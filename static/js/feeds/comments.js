function toggleComments(postId) {
    const commentsSection = document.getElementById(`comments-${postId}`);
    const isHidden = commentsSection.style.display === "none";

    if (isHidden) {
        commentsSection.style.display = "block";
        loadComments(postId);
    } else {
        commentsSection.style.display = "none";
    }
}

function loadComments(postId) {
    const container = document.querySelector(
        `#comments-${postId} .comments-container`
    );

    fetch(`/feeds/post/${postId}/comments/`)
        .then((response) => response.json())
        .then((data) => {
            container.innerHTML = data.html;
        })
        .catch((error) => console.error("Error:", error));
}

function submitComment(event, postId) {
    event.preventDefault();
    const form = event.target;
    const input = form.querySelector("input");
    const content = input.value.trim();

    if (!content) return;

    fetch(`/feeds/post/${postId}/comment/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ content }),
    })
        .then((response) => response.json())
        .then((data) => {
            input.value = "";
            loadComments(postId);
            
            const commentsCount = document.querySelector(`#post-${postId} .comments-count`);
            if (commentsCount) {
                commentsCount.textContent = data.comments_count;
            }
        })
        .catch((error) => console.error("Error:", error));
}

function toggleCommentLike(commentId, button) {
    fetch(`/feeds/comment/${commentId}/like/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCsrfToken(),
            "Content-Type": "application/json",
        },
    })
        .then((response) => response.json())
        .then((data) => {
            const likesCount = button.querySelector(".comment-likes-count");
            likesCount.textContent = data.likes_count;
            button.classList.toggle("text-danger", data.is_liked);
        })
        .catch((error) => console.error("Error:", error));
} 