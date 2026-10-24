import type { Api } from "./client";
import { createHttpApi } from "./http";

/** The one place that decides where data comes from. */
export const api: Api = createHttpApi();

export type { Api } from "./client";
export { ApiRequestError } from "./http";
