import { expect, test } from "@playwright/test";

test("creates and removes a task on the board", async ({ page }) => {
  // A unique title keeps the test idempotent against the shared dev database.
  const title = `Playwright smoke ${Date.now()}`;

  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Product launch board" }),
  ).toBeVisible();

  // Create a task using the Backlog column's on-demand form. Every column now
  // has its own "Add task" button, so target the first one (Backlog).
  await expect(page.getByPlaceholder("What needs doing?")).toHaveCount(0);
  await page.getByRole("button", { name: "Add task" }).first().click();

  const createForm = page.getByRole("form", { name: "Create task" });
  await expect(createForm.getByPlaceholder("What needs doing?")).toBeVisible();
  await createForm.getByPlaceholder("What needs doing?").fill(title);
  await createForm.getByRole("button", { name: "Add task" }).click();

  // The new card appears on the board.
  const card = page.getByRole("article", { name: `Task ${title}` });
  await expect(card).toBeVisible();

  // Remove it so the run leaves the database as it found it.
  await card.getByRole("button", { name: "Delete" }).click();
  await expect(card).toHaveCount(0);
});
