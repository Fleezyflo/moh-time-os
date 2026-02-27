// TabContainer — Reusable tab bar with content panels
// Extracted from ClientDetailSpec inline tab pattern

import { useState, type ReactNode } from 'react';

export interface TabDef<T extends string = string> {
  id: T;
  label: string;
  badge?: number;
}

interface TabContainerProps<T extends string> {
  tabs: TabDef<T>[];
  defaultTab?: T;
  activeTab?: T;
  onTabChange?: (tab: T) => void;
  children: (activeTab: T) => ReactNode;
}

export function TabContainer<T extends string>({
  tabs,
  defaultTab,
  activeTab: controlledTab,
  onTabChange,
  children,
}: TabContainerProps<T>) {
  const [internalTab, setInternalTab] = useState<T>(defaultTab ?? tabs[0].id);
  const activeTab = controlledTab ?? internalTab;

  const handleTabChange = (tab: T) => {
    if (onTabChange) {
      onTabChange(tab);
    } else {
      setInternalTab(tab);
    }
  };

  return (
    <div className="bg-[var(--grey-dim)] rounded-lg p-4">
      <div className="flex gap-1 border-b border-[var(--grey)] -mb-4 -mx-4 px-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`px-4 py-2 text-sm font-medium rounded-t transition-colors ${
              activeTab === tab.id
                ? 'bg-[var(--black)] text-[var(--white)]'
                : 'text-[var(--grey-light)] hover:text-[var(--white)] hover:bg-[var(--grey)]'
            }`}
          >
            {tab.label}
            {tab.badge != null && tab.badge > 0 && (
              <span className="ml-1.5 px-1.5 py-0.5 rounded text-xs bg-[var(--grey)] text-[var(--grey-light)]">
                {tab.badge}
              </span>
            )}
          </button>
        ))}
      </div>
      <div className="pt-4">{children(activeTab)}</div>
    </div>
  );
}
