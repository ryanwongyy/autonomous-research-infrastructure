import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RankChange } from "../rank-change";

describe("RankChange", () => {
  it("renders positive change with + prefix and green color", () => {
    const { container } = render(<RankChange change={3} />);
    const span = container.querySelector("span")!;
    expect(span.textContent).toBe("+3");
    expect(span.className).toContain("green");
  });

  it("renders negative change with red color", () => {
    const { container } = render(<RankChange change={-2} />);
    const span = container.querySelector("span")!;
    expect(span.textContent).toBe("-2");
    expect(span.className).toContain("red");
  });

  it("renders em-dash for zero change", () => {
    const { container } = render(<RankChange change={0} />);
    const span = container.querySelector("span")!;
    // &mdash; renders as "—"
    expect(span.textContent).toBe("—");
    expect(span.className).toContain("muted");
  });
});
