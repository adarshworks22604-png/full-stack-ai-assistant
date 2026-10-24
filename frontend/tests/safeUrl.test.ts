import { describe, expect, it } from "vitest";
import { safeUrl } from "../src/utils/safeUrl";

describe("safeUrl", () => {
  it("allows http and https", () => {
    expect(safeUrl("https://example.com/a")).toBe("https://example.com/a");
    expect(safeUrl("http://example.com/")).toBe("http://example.com/");
  });
  it.each(["javascript:alert(1)", "data:text/html,<script>1</script>", "file:///etc/passwd", "not a url", "", undefined])(
    "rejects %s",
    (value) => {
      expect(safeUrl(value)).toBeUndefined();
    },
  );
});
