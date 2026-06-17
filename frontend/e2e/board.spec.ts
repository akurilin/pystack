import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright";
import { expect, test } from "@playwright/test";

// Credentials for a Clerk dev-instance test user. global-setup.ts guarantees
// these are set (failing the suite with a clear message otherwise), so the test
// can use them directly.
const username = process.env.E2E_CLERK_USER_USERNAME!;
const password = process.env.E2E_CLERK_USER_PASSWORD!;

test("creates and removes a task on the board", async ({ page }) => {
  // A unique title keeps the test idempotent against the shared dev database.
  const title = `Playwright smoke ${Date.now()}`;

  // Sign in on the landing page, then open the board at its own route.
  await setupClerkTestingToken({ page });
  await page.goto("/");
  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: username,
      password: password,
    },
  });
  await page.goto("/board");

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
