export interface NavItemChild {
  label: string;
  icon: string;
  badge?: number;
  active?: boolean;
}

export interface NavItem {
  section: string;
  items: NavItemChild[];
}
