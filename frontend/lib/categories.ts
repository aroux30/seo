import { api } from "@/lib/api-client";

// ---------------------------------------------------------------- vocabularies

/** Mirrors CATEGORY_SOURCES in backend/app/models/categories.py. */
export type CategorySource = "manual" | "wordpress";

export const CATEGORY_SOURCE_LABELS_FA: Record<string, string> = {
  manual: "دستی",
  wordpress: "وردپرس",
};

// -------------------------------------------------------------------- entities

/** Flat row, mirrors CategoryRead in backend/app/schemas/categories.py. */
export interface CategoryRow {
  id: string;
  organization_id: string;
  website_id: string;
  parent_id: string | null;
  name: string;
  slug: string;
  description: string | null;
  path: string;
  depth: number;
  sort_order: number;
  wp_term_id: number | null;
  source: CategorySource | string;
  content_count: number;
}

/** Recursive shape, mirrors CategoryNode (CategoryRead + children). */
export interface CategoryNode extends CategoryRow {
  children: CategoryNode[];
}

export interface CategorySummary {
  total: number;
  roots: number;
  max_depth: number;
  by_source: Record<string, number>;
}

export interface CategoryDeleteResult {
  deleted: number;
}

export interface CategoryImportResult {
  created: number;
  updated: number;
  skipped: number;
}

// ----------------------------------------------------------------- write bodies

export interface CategoryCreateBody {
  website_id: string;
  parent_id?: string | null;
  name: string;
  slug?: string | null;
  description?: string | null;
  sort_order?: number;
}

export interface CategoryUpdateBody {
  name?: string | null;
  slug?: string | null;
  description?: string | null;
  sort_order?: number | null;
}

// ---------------------------------------------------------------------- helpers

/**
 * Flatten a tree into rows carrying their depth, in display order (parent
 * before children, siblings by their existing order). The backend already
 * sorts children by sort_order then name, so we preserve array order and only
 * annotate depth for indentation.
 */
export function flattenTree(nodes: CategoryNode[]): CategoryNode[] {
  const out: CategoryNode[] = [];
  const walk = (list: CategoryNode[]) => {
    for (const node of list) {
      out.push(node);
      if (node.children && node.children.length > 0) {
        walk(node.children);
      }
    }
  };
  walk(nodes);
  return out;
}

// ----------------------------------------------------------------------- calls

export function getCategoryTree(websiteId: string) {
  return api.get<CategoryNode[]>(`/categories/tree?website_id=${websiteId}`);
}

export function getCategorySummary(websiteId: string) {
  return api.get<CategorySummary>(`/categories/summary?website_id=${websiteId}`);
}

export function createCategory(body: CategoryCreateBody) {
  return api.post<CategoryRow>(`/categories`, body);
}

export function updateCategory(categoryId: string, body: CategoryUpdateBody) {
  return api.patch<CategoryRow>(`/categories/${categoryId}`, body);
}

export function moveCategory(categoryId: string, newParentId: string | null) {
  return api.post<CategoryRow>(`/categories/${categoryId}/move`, {
    new_parent_id: newParentId,
  });
}

export function deleteCategory(categoryId: string) {
  return api.delete<CategoryDeleteResult>(`/categories/${categoryId}`);
}

export function importWordpressCategories(websiteId: string) {
  return api.post<CategoryImportResult>(
    `/categories/import/wordpress?website_id=${websiteId}`,
    {}
  );
}
