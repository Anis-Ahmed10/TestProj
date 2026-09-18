"use client";

import React from "react";
import {
  FireOutlined,
  SyncOutlined,
  AppstoreOutlined,
  PlusOutlined,
} from "@ant-design/icons";
import type { CategoryConfig, CategoryKey } from "@/types/automationCandidate";

interface CategoryCardsProps {
  categories: Record<CategoryKey, CategoryConfig>;
  categoryOrder: CategoryKey[];
  activeCategory: CategoryKey;
  onSelectCategory: (key: CategoryKey) => void;
  onAddCategory: () => void;
}

const iconMap: Record<string, React.ElementType> = {
  FireOutlined,
  SyncOutlined,
  AppstoreOutlined,
};

export default function CategoryCards({
  categories,
  categoryOrder,
  activeCategory,
  onSelectCategory,
  onAddCategory,
}: CategoryCardsProps) {
  return (
    <div className="as-cat-cards">
      {categoryOrder.map((key) => {
        const cat = categories[key];
        if (!cat) return null;
        const Icon = iconMap[cat.icon] || AppstoreOutlined;
        const isActive = key === activeCategory;

        return (
          <div
            key={key}
            className={`as-cat-card${isActive ? " as-cat-card--active" : ""}`}
            onClick={() => onSelectCategory(key)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectCategory(key);
              }
            }}
          >
            <div className="as-cat-card-header">
              <div className="as-cat-label">
                {cat.title.replace(" Suite", "")}
              </div>
              <div className={`as-cat-icon ${cat.iconBgClass}`}>
                <Icon />
              </div>
            </div>
            <div className="as-cat-total">{cat.counts.all}</div>
            <div className="as-cat-total-label">Test cases evaluated</div>
            <div className="as-cat-breakdown">
              <span className="as-cb-chip as-cb-a">
                ✔ Automate {cat.counts.automate}
              </span>
              <span className="as-cb-chip as-cb-r">
                ⚑ Review {cat.counts.review}
              </span>
              <span className="as-cb-chip as-cb-m">
                ✗ Manual {cat.counts.manual}
              </span>
            </div>
          </div>
        );
      })}

      {/* Add Category card */}
      <button className="as-add-category" onClick={onAddCategory} type="button">
        <PlusOutlined />
        <span>Add Category</span>
      </button>
    </div>
  );
}
