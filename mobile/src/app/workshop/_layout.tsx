import { RoleTabs } from '../../components/Tabs';

export default function WorkshopLayout() {
  return (
    <RoleTabs role="workshop" tabs={[
      { name: 'index', title: 'tab_feed', icon: 'map' },
      { name: 'jobs', title: 'tab_jobs', icon: 'pricetags' },
      { name: 'profile', title: 'tab_profile', icon: 'person-circle' },
    ]} />
  );
}
