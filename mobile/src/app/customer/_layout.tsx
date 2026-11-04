import { RoleTabs } from '../../components/Tabs';

export default function CustomerLayout() {
  return (
    <RoleTabs role="customer" tabs={[
      { name: 'index', title: 'tab_requests', icon: 'list' },
      { name: 'new', title: 'tab_new', icon: 'camera' },
      { name: 'profile', title: 'tab_profile', icon: 'person-circle' },
    ]} />
  );
}
