interface TabNavigationProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export function TabNavigation({ activeTab, onTabChange }: TabNavigationProps) {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard' },
    { id: 'settings', label: 'Settings' }
  ];

  return (
    <div className="border-b border-slate-800">
      <nav className="flex space-x-4" aria-label="Tabs">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`px-3 py-2 text-sm font-medium border-b-2 ${
              activeTab === tab.id
                ? 'text-blue-300 border-blue-300'
                : 'text-slate-400 border-transparent hover:text-slate-300 hover:border-slate-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
} 