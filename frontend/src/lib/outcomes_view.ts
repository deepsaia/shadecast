/** Whether the outcomes row shows the numbers or the curves, kept in this browser like the threshold. */

export type OutcomesView = "numbers" | "curves";
const KEY = "shadecast.outcomes-view";

export function readOutcomesView(): OutcomesView {
  try {
    return window.localStorage.getItem(KEY) === "curves" ? "curves" : "numbers";
  } catch {
    return "numbers";
  }
}

export function storeOutcomesView(view: OutcomesView): void {
  try {
    window.localStorage.setItem(KEY, view);
  } catch {
    // storage may be blocked or absent; the choice holds for this visit
  }
}
