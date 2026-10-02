import type { ProjectDraft } from "@/features/project/types/project.types";

export interface FactoryContext {
  factoryId?: string;
  draft: ProjectDraft | null;
}

/** Resolves the backend factory id and its draft from a route id that may be a project or factory id. */
export function resolveFactoryContext(
  drafts: ProjectDraft[],
  routeId?: string | null,
  queryFactoryId?: string | null
): FactoryContext {
  const draft =
    drafts.find((d) => d.projectId === routeId) ??
    drafts.find((d) => Boolean(routeId) && d.factoryId === routeId) ??
    null;
  return {
    factoryId: queryFactoryId || draft?.factoryId || routeId || undefined,
    draft,
  };
}
