import { byName } from "./order";

it("orders by name regardless of case and leaves the given list alone", () => {
  const given = [{ name: "Rio de Janeiro" }, { name: "ahmedabad" }, { name: "London" }, { name: "Boston" }];
  expect(byName(given).map((item) => item.name)).toEqual(["ahmedabad", "Boston", "London", "Rio de Janeiro"]);
  expect(given[0].name).toBe("Rio de Janeiro");
});
