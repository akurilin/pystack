import { expect, test } from "@playwright/test";

test("creates and removes a task on the board", async ({ page }) => {
  // A unique title keeps the test idempotent against the shared dev database.
  const title = `Playwright smoke ${Date.now()}`;

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Product launch board" }),
  ).toBeVisible();

  // Create a task using the Backlog column's form.
  await page.getByPlaceholder("What needs doing?").fill(title);
  await page.getByRole("button", { name: "Add task" }).click();

  // The new card appears on the board.
  const card = page.locator("article.task-card").filter({ hasText: title });
  await expect(card).toBeVisible();

  // Remove it so the run leaves the database as it found it.
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(card).toHaveCount(0);
});
