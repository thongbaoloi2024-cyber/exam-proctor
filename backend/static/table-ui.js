const TableUI = {
  createState({ pageSize = 10, sortKey = "", sortDirection = "ascending" } = {}) {
    return { page: 1, pageSize, sortKey, sortDirection };
  },

  compare(left, right, type = "text") {
    const leftEmpty = left == null || left === "";
    const rightEmpty = right == null || right === "";
    if (leftEmpty || rightEmpty) {
      if (leftEmpty && rightEmpty) return 0;
      return leftEmpty ? 1 : -1;
    }
    if (type === "number") return Number(left) - Number(right);
    if (type === "date") {
      const leftTime = new Date(left).getTime();
      const rightTime = new Date(right).getTime();
      if (!Number.isNaN(leftTime) && !Number.isNaN(rightTime)) return leftTime - rightTime;
    }
    return String(left).localeCompare(String(right), "vi", { numeric: true, sensitivity: "base" });
  },

  sortItems(items, state, columns) {
    const column = columns[state.sortKey];
    if (!column) return [...items];
    const value = typeof column === "function" ? column : column.value;
    const type = typeof column === "function" ? "text" : column.type || "text";
    const direction = state.sortDirection === "descending" ? -1 : 1;
    return items
      .map((item, index) => ({ item, index }))
      .sort((left, right) => {
        const compared = this.compare(value(left.item), value(right.item), type);
        return compared ? compared * direction : left.index - right.index;
      })
      .map(({ item }) => item);
  },

  paginate(items, state) {
    const totalPages = Math.max(1, Math.ceil(items.length / state.pageSize));
    state.page = Math.min(Math.max(1, state.page), totalPages);
    const start = (state.page - 1) * state.pageSize;
    return {
      items: items.slice(start, start + state.pageSize),
      page: state.page,
      totalPages,
      totalItems: items.length,
      firstItem: items.length ? start + 1 : 0,
      lastItem: Math.min(start + state.pageSize, items.length),
    };
  },

  hidePagination(containerId) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.classList.add("hidden");
    container.replaceChildren();
  },

  renderPagination(containerId, pageData, onPageChange) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!pageData.totalItems) return this.hidePagination(containerId);
    const label = document.createElement("span");
    label.textContent = `Hiển thị ${pageData.firstItem}–${pageData.lastItem} / ${pageData.totalItems} · Trang ${pageData.page} / ${pageData.totalPages}`;
    const actions = document.createElement("div");
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "secondary-button pagination-button";
    previous.textContent = "← Trước";
    previous.disabled = pageData.page <= 1;
    previous.addEventListener("click", () => onPageChange(pageData.page - 1));
    const next = document.createElement("button");
    next.type = "button";
    next.className = "secondary-button pagination-button";
    next.textContent = "Sau →";
    next.disabled = pageData.page >= pageData.totalPages;
    next.addEventListener("click", () => onPageChange(pageData.page + 1));
    actions.append(previous, next);
    container.replaceChildren(label, actions);
    container.classList.remove("hidden");
  },

  updateSortHeaders(tableId, state) {
    document.querySelectorAll(`#${tableId} th[data-sort-key]`).forEach((heading) => {
      const active = heading.dataset.sortKey === state.sortKey;
      heading.setAttribute("aria-sort", active ? state.sortDirection : "none");
      const indicator = heading.querySelector(".sort-indicator");
      if (indicator) {
        indicator.textContent = active
          ? (state.sortDirection === "ascending" ? "↑" : "↓")
          : "↕";
      }
    });
  },

  bindSort(tableId, state, onChange) {
    document.querySelectorAll(`#${tableId} th[data-sort-key]`).forEach((heading) => {
      const label = heading.textContent.trim();
      const button = document.createElement("button");
      button.type = "button";
      button.className = "table-sort-button";
      const labelNode = document.createElement("span");
      labelNode.textContent = label;
      const indicator = document.createElement("span");
      indicator.className = "sort-indicator";
      indicator.setAttribute("aria-hidden", "true");
      button.append(labelNode, indicator);
      button.addEventListener("click", () => {
        const key = heading.dataset.sortKey;
        if (state.sortKey === key) {
          state.sortDirection = state.sortDirection === "ascending" ? "descending" : "ascending";
        } else {
          state.sortKey = key;
          state.sortDirection = heading.dataset.sortDefault === "descending" ? "descending" : "ascending";
        }
        state.page = 1;
        this.updateSortHeaders(tableId, state);
        onChange();
      });
      heading.replaceChildren(button);
    });
    this.updateSortHeaders(tableId, state);
  },
};
