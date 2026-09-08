import { expect, Page, test } from "@playwright/test";

const topics = [{ id: 1, user_id: 1, name: "Biology", parent_id: null }, { id: 2, user_id: 1, name: "Physics", parent_id: null }];
const question = (id: number, topic_id = 1) => ({ id, topic_id, chunk_id: 1, source_chunk_ids: [1], question_text: `Question ${id}?`, difficulty: "medium", question_type: "short_answer" });
const progress = (topic_id: number) => ({ user_id: 1, topic_id, ease_factor: 2.5, interval_days: 1, streak: 1, next_review_at: "2026-10-01T12:00:00Z" });
const stats = { attempted: 5, correct: 4, accuracy: 80, activity_streak: 2, days: [] };
const session = (id: number, count = 2) => ({ id, topic_id: 1, document_id: null as number | null, title: id === 1 ? "Earlier questions" : `Saved session ${id}`, focus: null, difficulty: "medium", question_type: "short_answer", is_legacy: id === 1, created_at: "2026-09-07T12:00:00Z", question_count: count });

async function workspace(page: Page, status = "ready") {
  const state = {
    status, attempts: [] as any[], creates: [] as any[], uploads: 0, documentReads: 0, questionReads: [] as string[],
    docsCount: 3, summaries: 0, summaryStatus: "none", sessionRows: Array.from({ length: 8 }, (_, i) => session(i + 1, i === 0 ? 14 : 2)),
  };
  await page.addInitScript(() => localStorage.setItem("prepify_token", "test-token"));
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    const method = route.request().method();
    if (path === "/api/v1/topics/") return route.fulfill({ json: topics });
    if (path === "/api/v1/documents/") {
      const docs = Array.from({ length: state.docsCount }, (_, i) => ({ id: i + 1, user_id: 1, topic_id: 1, title: `Notes ${i + 1}`, source_type: ".txt", file_path: "notes.txt", status: state.status, uploaded_at: "2026-09-01T12:00:00Z" }));
      if (method === "POST") { state.uploads += 1; return route.fulfill({ status: 201, json: { ...docs[0], id: 20, title: "New upload" } }); }
      state.documentReads += 1;
      return route.fulfill({ json: docs });
    }
    if (path === "/api/v1/progress/stats") return route.fulfill({ json: stats });
    if (path === "/api/v1/progress/due") return route.fulfill({ json: topics.map((t) => ({ ...t, ...progress(t.id) })) });
    if (/\/progress\/\d+$/.test(path)) return route.fulfill({ json: progress(Number(path.split("/").pop())) });
    if (path === "/api/v1/study-sessions/") {
      if (method === "POST") {
        const body = route.request().postDataJSON(); state.creates.push(body);
        const row = { ...session(100 + state.creates.length, body.count), document_id: body.document_id, title: "Fresh practice" };
        state.sessionRows.unshift(row);
        return route.fulfill({ status: 201, json: { session: row, items: [question(row.id * 100)], total: row.question_count, page: 1, page_size: 1, attempts: [] } });
      }
      const pageNum = Number(url.searchParams.get("page") ?? 1);
      return route.fulfill({ json: { items: state.sessionRows.slice((pageNum - 1) * 6, pageNum * 6), page: pageNum, page_size: 6, total: state.sessionRows.length } });
    }
    if (/\/study-sessions\/\d+$/.test(path)) {
      state.questionReads.push(url.toString());
      const id = Number(path.split("/").pop());
      const pageNum = Number(url.searchParams.get("page") ?? 1);
      const row = state.sessionRows.find((item) => item.id === id)!;
      const q = question(id * 100 + pageNum - 1);
      return route.fulfill({ json: { session: row, items: [q], total: row.question_count, page: pageNum, page_size: 1, attempts: state.attempts.filter((a) => a.question_id === q.id) } });
    }
    if (path.endsWith("/answer")) return route.fulfill({ json: { question_id: Number(path.split("/")[4]), answer_text: "Reference explanation" } });
    if (path.endsWith("/attempt")) {
      const body = route.request().postDataJSON();
      const result = { ...body, id: state.attempts.length + 1, user_id: 1, question_id: Number(path.split("/")[4]), created_at: "2026-09-07T12:00:00Z", answer_text: "Reference explanation", next_review_at: progress(1).next_review_at };
      state.attempts.push(result);
      return route.fulfill({ status: 201, json: result });
    }
    if (path.endsWith("/summary")) {
      if (method === "POST") { state.summaries += 1; state.summaryStatus = "pending"; }
      return route.fulfill({ status: method === "POST" ? 202 : 200, json: { document_id: Number(path.split("/")[4]), status: state.summaryStatus, summary: state.summaryStatus === "ready" ? "Concise notes summary" : null } });
    }
    if (path.endsWith("/content")) {
      const pageNum = Number(url.searchParams.get("page") ?? 1);
      return route.fulfill({ json: { document_id: 1, title: "Notes 1", content: pageNum === 1 ? "First original page" : "Second original page", page: pageNum, page_size: 4000, total_pages: 2, total_characters: 5000 } });
    }
    return route.fulfill({ status: 404, json: { detail: "Unexpected request" } });
  });
  return state;
}

async function openWorkspace(page: Page) {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Biology", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Refresh", exact: true })).toBeEnabled();
}
async function create(page: Page) {
  await page.getByRole("button", { name: "Create session", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Question 10100?", exact: true })).toBeVisible();
}

test("new questions use one batch request and do not mix with old questions", async ({ page }) => {
  const state = await workspace(page);
  await openWorkspace(page);
  await expect(page.locator(".question-box")).toHaveCount(0);
  expect(state.questionReads).toHaveLength(0);
  await create(page);
  expect(state.creates).toHaveLength(1);
  expect(state.creates[0].count).toBe(3);
  await expect(page.getByText("Question 1 of 3", { exact: true })).toBeVisible();
  await expect(page.locator(".question-box")).toHaveCount(1);
  await page.getByRole("button", { name: "Next question", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Question 10101?", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Question 100?", exact: true })).toHaveCount(0);
});

test("history is paginated and an old session can jump directly to its last question", async ({ page }) => {
  await workspace(page); await openWorkspace(page);
  await page.getByRole("tab", { name: "Study sessions", exact: true }).click();
  await expect(page.locator(".session-card")).toHaveCount(6);
  await page.getByRole("button", { name: "Next sessions" }).click();
  await expect(page.locator(".session-card")).toHaveCount(2);
  await page.getByRole("button", { name: "Previous sessions" }).click();
  await page.locator(".session-card").filter({ has: page.getByRole("heading", { name: "Earlier questions", exact: true }) }).getByRole("button", { name: "Open session" }).click();
  await expect(page.getByText("Question 1 of 14", { exact: true })).toBeVisible();
  await page.getByLabel("Go to question", { exact: true }).fill("14");
  await page.getByRole("button", { name: "Go", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Question 113?", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Next question" })).toBeDisabled();
});

test("practice specific notes sends the document filter with the session", async ({ page }) => {
  const state = await workspace(page); await openWorkspace(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.locator(".session-card").filter({ has: page.getByRole("heading", { name: "Notes 2", exact: true }) }).getByRole("button", { name: "Practice these notes" }).click();
  await expect(page.getByLabel("Use notes", { exact: true })).toHaveValue("2");
  await page.getByPlaceholder("Optional focus query").fill("Evaporation");
  await create(page);
  expect(state.creates[0].document_id).toBe(2);
  expect(state.creates[0].query).toBe("Evaporation");
});

test("reveal precedes rating; question navigation and reopening retain recorded attempts", async ({ page }) => {
  const state = await workspace(page); await openWorkspace(page); await create(page);
  await expect(page.getByRole("button", { name: "I got it right" })).toHaveCount(0);
  await page.locator("textarea").fill("My answer");
  await page.getByRole("button", { name: "Next question" }).click();
  await page.getByRole("button", { name: "Previous question" }).click();
  await expect(page.locator("textarea")).toHaveValue("My answer");
  await page.getByRole("button", { name: "Reveal answer" }).click();
  await expect(page.getByText("Reference explanation", { exact: true })).toBeVisible();
  expect(state.attempts).toHaveLength(0);
  await page.getByRole("button", { name: "I got it right" }).click();
  await expect(page.getByText(/Recorded as correct/)).toBeVisible();
  await page.reload();
  await page.getByRole("tab", { name: "Study sessions", exact: true }).click();
  await page.locator(".session-card").filter({ hasText: "Fresh practice" }).getByRole("button", { name: "Open session" }).click();
  await expect(page.getByText(/Recorded as correct/)).toBeVisible();
  expect(state.attempts).toHaveLength(1);
});

test("a lost generation response retries with the same request ID", async ({ page }) => {
  const state = await workspace(page);
  const bodies: any[] = [];
  await page.route("**/study-sessions/", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    bodies.push(route.request().postDataJSON());
    if (bodies.length === 1) return route.abort("failed");
    return route.fallback();
  });
  await openWorkspace(page);
  await page.getByRole("button", { name: "Create session", exact: true }).click();
  await expect(page.getByText(/Cannot reach the server/)).toBeVisible();
  await create(page);
  expect(bodies[0]).toEqual(bodies[1]);
  expect(state.creates).toHaveLength(1);
});

test("a lost rating response retries with an identical submission", async ({ page }) => {
  await workspace(page);
  const bodies: any[] = [];
  await page.route("**/practice/*/attempt", async (route) => {
    bodies.push(route.request().postDataJSON());
    if (bodies.length === 1) return route.abort("failed");
    return route.fallback();
  });
  await openWorkspace(page); await create(page);
  await page.getByRole("button", { name: "Reveal answer" }).click();
  await page.getByRole("button", { name: "I got it right" }).click();
  await expect(page.getByRole("button", { name: "I missed it" })).toBeDisabled();
  await page.getByRole("button", { name: "Retry correct rating" }).click();
  await expect(page.getByText(/Recorded as correct/)).toBeVisible();
  expect(bodies[0]).toEqual(bodies[1]);
});

test("notes have a separate reader, summary polling, and paginated originals", async ({ page }) => {
  const state = await workspace(page); await openWorkspace(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.locator(".session-card").first().getByRole("button", { name: "Read notes" }).click();
  await expect(page.getByRole("heading", { name: "Notes 1", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Summarize notes", exact: true }).click();
  await expect(page.getByText(/Summarizing your notes/)).toBeVisible();
  state.summaryStatus = "ready";
  await expect(page.getByText("Concise notes summary", { exact: true })).toBeVisible({ timeout: 6000 });
  await page.getByRole("button", { name: "View original notes" }).click();
  await expect(page.getByText("First original page", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Next page", exact: true }).click();
  await expect(page.getByText("Second original page", { exact: true })).toBeVisible();
  await expect(page.getByText("First original page", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "← Back to notes" }).click();
  await page.locator(".session-card").first().getByRole("button", { name: "Read notes" }).click();
  await expect(page.getByText("Concise notes summary", { exact: true })).toBeVisible();
  expect(state.summaries).toBe(1);
});

test("notes library paginates and filters document titles", async ({ page }) => {
  const state = await workspace(page); state.docsCount = 9;
  await openWorkspace(page); await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await expect(page.locator(".session-card")).toHaveCount(6);
  await page.getByRole("button", { name: "Next notes" }).click();
  await expect(page.locator(".session-card")).toHaveCount(3);
  await page.getByLabel("Filter notes by title").fill("Notes 2");
  await expect(page.locator(".session-card")).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "Notes 2", exact: true })).toBeVisible();
});

test("processing gates generation and polling enables it", async ({ page }) => {
  const state = await workspace(page, "processing"); await openWorkspace(page);
  await expect(page.getByRole("button", { name: "Create session", exact: true })).toBeDisabled();
  state.status = "ready";
  await expect(page.getByRole("button", { name: "Create session", exact: true })).toBeEnabled({ timeout: 6000 });
  expect(state.documentReads).toBeGreaterThan(1);
});

test("upload accepts pdfs, clears the file input, and prevents another submission", async ({ page }) => {
  const state = await workspace(page); await openWorkspace(page);
  await page.getByRole("tab", { name: "Notes", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "notes.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4") });
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await expect(page.getByText(/Upload queued/)).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveValue("");
  await expect(page.getByRole("button", { name: "Upload", exact: true })).toBeDisabled();
  expect(state.uploads).toBe(1);
});

test("expired sessions return to login", async ({ page }) => {
  await workspace(page);
  await page.route("**/api/v1/topics/", (route) => route.fulfill({ status: 401, json: { detail: "Expired" } }));
  await page.goto("/");
  await expect(page.getByText("Your session expired. Please log in again.")).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem("prepify_token"))).toBeNull();
});

test("generation errors keep the active session intact and show a readable notice", async ({ page }) => {
  await workspace(page); await openWorkspace(page); await create(page);
  await page.route("**/study-sessions/", (route) => route.fulfill({ status: 502, json: { detail: "The model repeated an existing question. Try a different focus." } }));
  await page.getByRole("button", { name: "Create session", exact: true }).click();
  await expect(page.getByText(/The model repeated/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Question 10100?", exact: true })).toBeVisible();
});

test("logout invalidates a late generation response", async ({ page }) => {
  await workspace(page);
  let release!: () => void;
  let started!: () => void;
  const held = new Promise<void>((resolve) => { release = resolve; });
  const requested = new Promise<void>((resolve) => { started = resolve; });
  await page.route("**/study-sessions/", async (route) => { started(); await held; await route.fallback(); });
  await openWorkspace(page);
  await page.getByRole("button", { name: "Create session", exact: true }).click();
  await requested;
  await page.getByRole("button", { name: "Logout", exact: true }).click();
  const response = page.waitForResponse("**/study-sessions/"); release(); await response;
  await expect(page.getByLabel("Email", { exact: true })).toBeVisible();
  await expect(page.locator(".question-box")).toHaveCount(0);
});

test("summary status fetch failure offers Retry and recovers", async ({ page }) => {
  const state = await workspace(page);
  let failing = true;
  await page.route('**/documents/*/summary', route => failing
    ? route.fulfill({ status: 503, json: { detail: 'Temporarily unavailable' } })
    : route.fallback());
  await openWorkspace(page);
  await page.getByRole('tab', {name:'Notes',exact:true}).click();
  await page.locator('.session-card').first().getByRole('button',{name:'Read notes'}).click();
  await expect(page.getByText('Could not refresh the summary status. Retry or read the original notes.')).toBeVisible();
  await expect(page.getByText('Loading summary…',{exact:true})).toHaveCount(0);
  failing = false; state.summaryStatus = 'ready';
  const response = page.waitForResponse('**/documents/*/summary');
  await page.getByRole('button',{name:'Retry',exact:true}).click(); await response;
  await expect(page.getByText('Concise notes summary',{exact:true})).toBeVisible();
});

for (const status of ['pending','processing']) {
  test(`Retry rechecks ${status} summary state from the server`, async ({page}) => {
    const state = await workspace(page); state.summaryStatus = status;
    await openWorkspace(page);
    await page.getByRole('tab',{name:'Notes',exact:true}).click();
    await page.locator('.session-card').first().getByRole('button',{name:'Read notes'}).click();
    await expect(page.getByRole('button',{name:'Retry',exact:true})).toBeEnabled();
    state.summaryStatus = 'failed';
    const response = page.waitForResponse('**/documents/*/summary');
    await page.getByRole('button',{name:'Retry',exact:true}).click(); await response;
    await expect(page.getByRole('button',{name:'Retry summary',exact:true})).toBeVisible();
    await page.getByRole('button',{name:'Retry summary',exact:true}).click();
    expect(state.summaries).toBe(1);
  });
}

test('dark interface renders summary Markdown safely and fits mobile', async ({page}) => {
  await workspace(page);
  await page.setViewportSize({width:1440,height:1100});
  await openWorkspace(page);
  await page.screenshot({path:'/tmp/prepify-dark-practice.png',fullPage:true});
  await page.route('**/documents/*/summary', route => route.fulfill({json:{document_id:1,status:'ready',summary:'## Water cycle\n\n**Solar energy** powers evaporation.\n\n- Evaporation\n- Condensation\n\n| Process | Result |\n| --- | --- |\n| Cooling | Clouds |\n\n<script>window.markdownExecuted = true</script>\n\n![tracking](https://example.com/tracker.png)'}}));
  await page.getByRole('tab',{name:'Notes',exact:true}).click();
  await page.locator('.session-card').first().getByRole('button',{name:'Read notes'}).click();
  await expect(page.locator('.markdown-content h2')).toHaveText('Water cycle');
  await expect(page.locator('.markdown-content strong')).toHaveText('Solar energy');
  await expect(page.locator('.markdown-content li')).toHaveCount(2);
  await expect(page.locator('.markdown-content table')).toBeVisible();
  await expect(page.locator('.markdown-content script, .markdown-content img')).toHaveCount(0);
  expect(await page.evaluate(()=>getComputedStyle(document.documentElement).colorScheme)).toBe('dark');
  await page.screenshot({path:'/tmp/prepify-dark-reader.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path:'/tmp/prepify-dark-mobile.png',fullPage:true});
});
