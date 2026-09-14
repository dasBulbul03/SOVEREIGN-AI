import { describe, expect, it } from "vitest";

import { desiredIndexFileIds, formatContextWindow } from "./api";

describe("formatContextWindow", () => {
  it("formats model context clearly", () => {
    expect(formatContextWindow(32768)).toBe("32K");
    expect(formatContextWindow(null)).toBe("Unknown");
  });
});

describe("desiredIndexFileIds", () => {
  it("preserves only the selected library membership when adding a file", () => {
    const files = [
      { id: "already-in-this-library", indexed: true },
      { id: "workspace-file-from-elsewhere", indexed: false },
    ];

    expect(desiredIndexFileIds(files, "new-file")).toEqual([
      "already-in-this-library",
      "new-file",
    ]);
  });

  it("does not duplicate a file that is already indexed", () => {
    expect(desiredIndexFileIds([{ id: "same-file", indexed: true }], "same-file")).toEqual([
      "same-file",
    ]);
  });
});
