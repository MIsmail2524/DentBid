import { LANGUAGES, Lang, useLocale } from '../i18n';
import { api } from '../lib/api';
import { useAuth } from '../lib/auth';
import { Chip, Row } from './ui';

export function LanguagePicker() {
  const { language, setLanguage } = useLocale();
  const { user, setUser } = useAuth();
  const pick = (l: Lang) => {
    setLanguage(l);
    if (user) api.updateMe({ language: l }).then(setUser).catch(() => undefined);
  };
  return (
    <Row wrap style={{ justifyContent: 'center' }}>
      {(Object.keys(LANGUAGES) as Lang[]).map((l) => (
        <Chip key={l} label={LANGUAGES[l]} active={language === l} onPress={() => pick(l)} />
      ))}
    </Row>
  );
}
