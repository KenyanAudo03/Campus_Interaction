// Liking
window.toggleLike = async function (postId) {
  const likeElement = document.querySelector(
    `#post-${postId} .stat-item.likes`
  );
  const likeIcon = likeElement.querySelector("i");
  const likeCountElement = likeElement.querySelector("span");
  try {
    const response = await fetch(`/forums/post/${postId}/like/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
          .value,
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    if (response.ok) {
      likeCountElement.textContent = data.like_count;
      if (data.status === "liked") {
        likeIcon.classList.add("liked");
      } else {
        likeIcon.classList.remove("liked");
      }
    } else {
      console.error("Failed to toggle like:", data);
    }
  } catch (error) {
    console.error("Error:", error);
  }
};

document.addEventListener("DOMContentLoaded", function () {
  const textarea = document.querySelector("#post-form textarea");

  if (textarea) {
    textarea.addEventListener("keydown", function (e) {
      if (e.key === "Tab") {
        e.preventDefault();
        const start = this.selectionStart;
        const end = this.selectionEnd;
        this.value =
          this.value.substring(0, start) + "\t" + this.value.substring(end);

        this.selectionStart = this.selectionEnd = start + 1;
      }
    });
  }
});

// Searching for Posts
document.addEventListener("DOMContentLoaded", function () {
  const searchInput = document.getElementById("forum-search-input");
  const suggestionsContainer = document.getElementById("search-suggestions");
  const forumId = searchInput.getAttribute("data-forum-id");

  let debounceTimer;
  let cachedSuggestions = [];
  let lastQuery = "";

  searchInput.addEventListener("focus", function () {
    searchInput.classList.add("focused");
    if (
      cachedSuggestions.length > 0 &&
      searchInput.value.trim() === lastQuery
    ) {
      displaySuggestions(cachedSuggestions);
    }
  });

  searchInput.addEventListener("blur", function () {
    searchInput.classList.remove("focused");

    setTimeout(() => {
      suggestionsContainer.style.display = "none";
    }, 200);
  });

  searchInput.addEventListener("input", function () {
    clearTimeout(debounceTimer);

    const query = this.value.trim();
    if (query.length < 2) {
      suggestionsContainer.innerHTML = "";
      suggestionsContainer.style.display = "none";
      cachedSuggestions = [];
      lastQuery = "";
      return;
    }

    debounceTimer = setTimeout(() => {
      if (query === lastQuery) {
        displaySuggestions(cachedSuggestions);
        return;
      }

      fetch(
        `/forums/search/posts/?q=${encodeURIComponent(
          query
        )}&forum_id=${forumId}`
      )
        .then((response) => response.json())
        .then((data) => {
          if (data.suggestions.length === 0) {
            displayNoResults(query);
            return;
          }

          cachedSuggestions = data.suggestions;
          lastQuery = query;
          displaySuggestions(data.suggestions);
        })
        .catch((error) => {
          console.error("Search error:", error);
          displayErrorMessage();
        });
    }, 300);
  });

  function displayNoResults(query) {
    suggestionsContainer.innerHTML = "";
    const noResultsElement = document.createElement("div");
    noResultsElement.classList.add("no-results");
    noResultsElement.innerHTML = `
      <div style="padding: 15px; text-align: center; color: #6c757d;">
        <p>No results found for "<strong>${escapeHtml(query)}</strong>"</p>
        <small>Try different keywords or check your spelling</small>
      </div>
    `;
    suggestionsContainer.appendChild(noResultsElement);
    suggestionsContainer.style.display = "block";
    applyContainerStyles();
  }

  function displayErrorMessage() {
    suggestionsContainer.innerHTML = "";
    const errorElement = document.createElement("div");
    errorElement.classList.add("search-error");
    errorElement.innerHTML = `
      <div style="padding: 15px; text-align: center; color: #dc3545;">
        <p>An error occurred while searching</p>
        <small>Please try again later</small>
      </div>
    `;
    suggestionsContainer.appendChild(errorElement);
    suggestionsContainer.style.display = "block";
    applyContainerStyles();
  }

  function escapeHtml(unsafe) {
    return unsafe
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function displaySuggestions(suggestions) {
    suggestionsContainer.innerHTML = "";

    suggestions.forEach((suggestion) => {
      const suggestionElement = document.createElement("div");
      suggestionElement.classList.add("search-suggestion");

      suggestionElement.innerHTML = `
  <a href="${
    suggestion.url
  }" class="suggestion-link" style="display: flex; align-items: center;">
    ${
      suggestion.media
        ? `<div class="media-container" style="margin-right: 10px; position: relative; width: 50px; height: 50px;">
           ${
             suggestion.media.endsWith(".mp4") ||
             suggestion.media.endsWith(".webm") ||
             suggestion.media.endsWith(".mov") ||
             suggestion.media.endsWith(".avi") ||
             suggestion.media.endsWith(".ogg")
               ? `<video src="${suggestion.media}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" controls></video>`
               : `<img src="${suggestion.media}" alt="Media" style="width: 50px; height: 50px; object-fit: cover; border-radius: 5px;" />`
           }
         </div>`
        : ""
    }
    <div class="suggestion-content">
      <strong>${suggestion.title}</strong>
      <small>created by ${suggestion.author} ${suggestion.created_at}</small>
    </div>
  </a>
`;
      suggestionElement.addEventListener("mouseover", () => {
        suggestionElement.style.backgroundColor = "#e9ecef";
      });

      suggestionElement.addEventListener("mouseout", () => {
        suggestionElement.style.backgroundColor = "#f8f9fa";
      });

      suggestionElement.addEventListener("click", () => {
        window.location.href = suggestion.url;
      });

      suggestionsContainer.appendChild(suggestionElement);
    });

    applyContainerStyles();
  }

  function applyContainerStyles() {
    suggestionsContainer.style.display = "block";
    suggestionsContainer.style.position = "absolute";
    suggestionsContainer.style.width = searchInput.offsetWidth + "px";
    suggestionsContainer.style.backgroundColor = "#fff";
    suggestionsContainer.style.border = "1px solid #dee2e6";
    suggestionsContainer.style.boxShadow = "0 4px 6px rgba(0,0,0,0.1)";
    suggestionsContainer.style.maxHeight = "300px";
    suggestionsContainer.style.overflowY = "auto";
    suggestionsContainer.style.zIndex = "4";
  }

  document.addEventListener("click", function (event) {
    if (
      !suggestionsContainer.contains(event.target) &&
      event.target !== searchInput
    ) {
      suggestionsContainer.style.display = "none";
    }
  });

  window.addEventListener("resize", function () {
    suggestionsContainer.style.width = searchInput.offsetWidth + "px";
  });
});
