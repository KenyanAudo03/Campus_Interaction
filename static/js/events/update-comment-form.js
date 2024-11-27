document.addEventListener("DOMContentLoaded", function () {
    const commentSection = document.getElementById("main-comments");
    const noCommentsPlaceholder = document.querySelector(".text-center.text-muted");

    // Function to check if comments exist and remove the placeholder
    function checkAndRemovePlaceholder() {
        const hasComments = commentSection.querySelectorAll(".comment").length > 0;

        if (hasComments && noCommentsPlaceholder) {
            noCommentsPlaceholder.remove(); // Remove the "No comments yet" placeholder
        }
    }

    // Call the function initially in case comments are loaded dynamically
    checkAndRemovePlaceholder();

    // Example: Simulating comment addition dynamically
    // This part should be replaced with the actual dynamic update logic
    document.getElementById("addCommentButton").addEventListener("click", function () {
        const newComment = document.createElement("div");
        newComment.className = "comment";
        newComment.textContent = "This is a new comment!";
        commentSection.appendChild(newComment);

        checkAndRemovePlaceholder(); // Re-check after adding a new comment
    });
});