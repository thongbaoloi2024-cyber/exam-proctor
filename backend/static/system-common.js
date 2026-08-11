const SystemUI = {
  colors: ["#6ea8fe", "#45d6a5", "#a78bfa", "#f3b55a", "#ef6a78", "#67c7e8", "#94a3b8"],

  async initialize(requiredCapability = "system.organizations.read") {
    const user = await API.requireAuth();
    if (!user) return null;
    if (!API.hasCapability(requiredCapability)) {
      const role = API.getRole();
      window.location.replace(
        role === "org_admin" || role === "admin"
          ? "/ui/organization/overview"
          : "/ui/exams/overview",
      );
      return null;
    }
    this.bindDialogs();
    return user;
  },

  async fetchJson(path, options = {}) {
    const response = await API.request(path, options);
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || "Không tải được dữ liệu hệ thống.");
    return payload;
  },

  bindDialogs() {
    document.querySelectorAll("dialog").forEach((dialog) => {
      dialog.querySelectorAll(".dialog-close").forEach((button) => {
        button.addEventListener("click", () => dialog.close());
      });
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    });
  },

  text(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value == null ? "–" : String(value);
  },

  formatNumber(value) {
    return new Intl.NumberFormat("vi-VN").format(Number(value || 0));
  },

  formatDate(value, withTime = false) {
    if (!value) return "–";
    const options = withTime
      ? { dateStyle: "short", timeStyle: "short" }
      : { day: "2-digit", month: "2-digit", year: "numeric" };
    return new Intl.DateTimeFormat("vi-VN", options).format(new Date(value));
  },

  shortDate(value) {
    if (!value) return "";
    return new Intl.DateTimeFormat("vi-VN", { day: "2-digit", month: "2-digit" }).format(
      new Date(`${value}T00:00:00Z`),
    );
  },

  cell(row, value, className = "") {
    const cell = document.createElement("td");
    cell.textContent = value == null || value === "" ? "–" : String(value);
    if (className) cell.className = className;
    row.appendChild(cell);
    return cell;
  },

  statusLabel(status) {
    return {
      active: "Hoạt động",
      suspended: "Tạm khóa",
      pending: "Chờ duyệt",
      expired: "Hết hạn",
      revoked: "Đã thu hồi",
      success: "Thành công",
      failed: "Thất bại",
      denied: "Bị từ chối",
    }[status] || status || "Không xác định";
  },

  badge(status, label = null) {
    const badge = document.createElement("span");
    badge.className = `status-badge status-${String(status || "neutral").replace(/[^a-z0-9_-]/gi, "")}`;
    badge.textContent = label || this.statusLabel(status);
    return badge;
  },

  empty(message) {
    const element = document.createElement("div");
    element.className = "empty-state compact";
    element.textContent = message;
    return element;
  },

  setBusy(button, busy, busyText = "Đang xử lý...") {
    if (!button) return;
    if (busy) {
      button.dataset.originalText = button.textContent;
      button.textContent = busyText;
      button.disabled = true;
    } else {
      button.textContent = button.dataset.originalText || button.textContent;
      button.disabled = false;
    }
  },

  svg(tag, attributes = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
    return element;
  },

  renderLineChart(containerId, points) {
    const container = document.getElementById(containerId);
    if (!container) return;
    if (!points?.length) {
      container.replaceChildren(this.empty("Chưa có dữ liệu trong khoảng thời gian này."));
      return;
    }
    const width = 720;
    const height = 230;
    const padding = { left: 42, right: 18, top: 18, bottom: 35 };
    const chartWidth = width - padding.left - padding.right;
    const chartHeight = height - padding.top - padding.bottom;
    const maxValue = Math.max(1, ...points.map((item) => Number(item.value || 0)));
    const svg = this.svg("svg", { viewBox: `0 0 ${width} ${height}`, class: "svg-chart", "aria-hidden": "true" });
    const plotPoints = points.map((item, index) => ({
      x: padding.left + (points.length === 1 ? chartWidth / 2 : (index / (points.length - 1)) * chartWidth),
      y: padding.top + chartHeight - (Number(item.value || 0) / maxValue) * chartHeight,
      item,
    }));
    for (let index = 0; index <= 4; index += 1) {
      const y = padding.top + (index / 4) * chartHeight;
      svg.appendChild(this.svg("line", { x1: padding.left, x2: width - padding.right, y1: y, y2: y, class: "chart-grid-line" }));
      const label = this.svg("text", { x: padding.left - 10, y: y + 4, "text-anchor": "end", class: "chart-axis-label" });
      label.textContent = String(Math.round(maxValue * (1 - index / 4)));
      svg.appendChild(label);
    }
    const area = this.svg("path", {
      d: `M ${plotPoints[0].x} ${padding.top + chartHeight} L ${plotPoints.map((point) => `${point.x} ${point.y}`).join(" L ")} L ${plotPoints[plotPoints.length - 1].x} ${padding.top + chartHeight} Z`,
      class: "chart-area",
    });
    const line = this.svg("path", {
      d: `M ${plotPoints.map((point) => `${point.x} ${point.y}`).join(" L ")}`,
      class: "chart-line-path",
    });
    svg.append(area, line);
    plotPoints.forEach((point, index) => {
      if (points.length <= 14 || index % Math.ceil(points.length / 7) === 0 || index === points.length - 1) {
        const label = this.svg("text", { x: point.x, y: height - 10, "text-anchor": "middle", class: "chart-axis-label" });
        label.textContent = this.shortDate(point.item.label);
        svg.appendChild(label);
      }
      const dot = this.svg("circle", { cx: point.x, cy: point.y, r: 3.4, class: "chart-point" });
      const title = this.svg("title");
      title.textContent = `${this.shortDate(point.item.label)}: ${this.formatNumber(point.item.value)}`;
      dot.appendChild(title);
      svg.appendChild(dot);
    });
    const summary = document.createElement("p");
    summary.className = "sr-only";
    summary.textContent = points.map((item) => `${item.label}: ${item.value}`).join(", ");
    container.replaceChildren(svg, summary);
  },

  renderDonutChart(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const total = (items || []).reduce((sum, item) => sum + Number(item.value || 0), 0);
    if (!total) {
      container.replaceChildren(this.empty("Chưa có dữ liệu để phân bổ."));
      return;
    }
    const wrapper = document.createElement("div");
    wrapper.className = "donut-layout";
    const visual = document.createElement("div");
    visual.className = "donut-visual";
    const svg = this.svg("svg", { viewBox: "0 0 120 120", class: "donut-svg", "aria-hidden": "true" });
    svg.appendChild(this.svg("circle", { cx: 60, cy: 60, r: 44, class: "donut-track" }));
    const circumference = 2 * Math.PI * 44;
    let offset = 0;
    items.forEach((item, index) => {
      const length = (Number(item.value || 0) / total) * circumference;
      const segment = this.svg("circle", {
        cx: 60,
        cy: 60,
        r: 44,
        class: "donut-segment",
        stroke: this.colors[index % this.colors.length],
        "stroke-dasharray": `${length} ${circumference - length}`,
        "stroke-dashoffset": -offset,
      });
      offset += length;
      svg.appendChild(segment);
    });
    const totalNode = document.createElement("div");
    totalNode.className = "donut-total";
    const totalValue = document.createElement("strong");
    totalValue.textContent = this.formatNumber(total);
    const totalLabel = document.createElement("span");
    totalLabel.textContent = "Tổng";
    totalNode.append(totalValue, totalLabel);
    visual.append(svg, totalNode);
    const legend = document.createElement("div");
    legend.className = "chart-legend";
    items.forEach((item, index) => {
      const row = document.createElement("div");
      const label = document.createElement("span");
      const dot = document.createElement("i");
      dot.style.backgroundColor = this.colors[index % this.colors.length];
      label.append(dot, document.createTextNode(item.label));
      const value = document.createElement("strong");
      value.textContent = this.formatNumber(item.value);
      row.append(label, value);
      legend.appendChild(row);
    });
    wrapper.append(visual, legend);
    container.replaceChildren(wrapper);
  },

  renderBarChart(containerId, items) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const maxValue = Math.max(0, ...(items || []).map((item) => Number(item.value || 0)));
    if (!items?.length || maxValue === 0) {
      container.replaceChildren(this.empty("Chưa có dữ liệu để so sánh."));
      return;
    }
    const chart = document.createElement("div");
    chart.className = "horizontal-bars";
    items.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "horizontal-bar-row";
      const meta = document.createElement("div");
      meta.className = "horizontal-bar-meta";
      const label = document.createElement("span");
      label.textContent = item.label || item.name || item.key;
      label.title = label.textContent;
      const value = document.createElement("strong");
      value.textContent = this.formatNumber(item.value);
      meta.append(label, value);
      const track = document.createElement("div");
      track.className = "horizontal-bar-track";
      const fill = document.createElement("span");
      fill.style.width = `${Math.max(2, (Number(item.value || 0) / maxValue) * 100)}%`;
      fill.style.backgroundColor = this.colors[index % this.colors.length];
      track.appendChild(fill);
      row.append(meta, track);
      chart.appendChild(row);
    });
    container.replaceChildren(chart);
  },

  renderPagination(containerId, page, pages, onPage) {
    const container = document.getElementById(containerId);
    if (!container) return;
    const label = document.createElement("span");
    label.textContent = `Trang ${page} / ${pages}`;
    const actions = document.createElement("div");
    const previous = document.createElement("button");
    previous.type = "button";
    previous.className = "secondary-button pagination-button";
    previous.textContent = "← Trước";
    previous.disabled = page <= 1;
    previous.addEventListener("click", () => onPage(page - 1));
    const next = document.createElement("button");
    next.type = "button";
    next.className = "secondary-button pagination-button";
    next.textContent = "Sau →";
    next.disabled = page >= pages;
    next.addEventListener("click", () => onPage(page + 1));
    actions.append(previous, next);
    container.replaceChildren(label, actions);
  },
};
