import { describe, it, expect } from "vitest";
import { cn } from "@/lib/utils";

describe("cn()", () => {
  it("merges simple class strings", () => {
    expect(cn("foo", "bar")).toBe("foo bar");
  });

  it("handles conditional classes (clsx style)", () => {
    expect(cn("base", false && "hidden", "visible")).toBe("base visible");
  });

  it("handles truthy conditional classes", () => {
    const isActive = true;
    expect(cn("btn", isActive && "btn-active")).toBe("btn btn-active");
  });

  it("resolves Tailwind conflicts via twMerge", () => {
    // twMerge should keep the later class when they conflict
    expect(cn("text-red-500", "text-blue-500")).toBe("text-blue-500");
  });

  it("merges padding shorthand correctly", () => {
    // p-3 should override px-2 py-1 since p covers both axes
    expect(cn("px-2 py-1", "p-3")).toBe("p-3");
  });

  it("returns empty string for no arguments", () => {
    expect(cn()).toBe("");
  });

  it("handles undefined and null inputs gracefully", () => {
    expect(cn("foo", undefined, null, "bar")).toBe("foo bar");
  });

  it("handles array of classes", () => {
    expect(cn(["foo", "bar"], "baz")).toBe("foo bar baz");
  });

  it("handles object syntax for conditionals", () => {
    expect(cn({ hidden: false, visible: true, "font-bold": true })).toBe(
      "visible font-bold"
    );
  });
});
