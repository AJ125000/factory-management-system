import { Button, Menu } from '@mantine/core';
import { IconFileSpreadsheet } from '@tabler/icons-react';
import { useTranslation } from 'react-i18next';

import { exportUrl } from '../api/hooks';

/** "Download Excel" with a choice of English or Hindi headings. */
export function ExportMenu({
  kind,
  params,
  disabled,
}: {
  kind: 'wages' | 'production';
  params: Record<string, string | string[] | undefined>;
  disabled?: boolean;
}) {
  const { t } = useTranslation();
  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button variant="default" leftSection={<IconFileSpreadsheet size={18} />} disabled={disabled}>
          {t('reports.excel')}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {(['en', 'hi'] as const).map((lang) => (
          <Menu.Item key={lang} component="a" href={exportUrl(kind, { ...params, lang })} download>
            {t(`lang.${lang}`)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
