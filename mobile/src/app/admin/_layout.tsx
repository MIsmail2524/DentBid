import { RoleTabs } from '../../components/Tabs';

export default function AdminLayout() {
  return (
    <RoleTabs role="admin" tabs={[
      { name: 'index', title: 'tab_admin_queue', icon: 'shield-checkmark' },
      { name: 'workshops', title: 'tab_admin_workshops', icon: 'construct' },
      { name: 'users', title: 'tab_admin_users', icon: 'people' },
      { name: 'profile', title: 'tab_profile', icon: 'person-circle' },
    ]} />
  );
}
