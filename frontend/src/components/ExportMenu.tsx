import { Button, Menu } from '@mantine/core';
import { IconFileSpreadsheet } from '@tabler/icons-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';

import { downloadFile } from '../api/client';
import { notifyError } from './common';

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
  const [busy, setBusy] = useState(false);

  const download = async (lang: 'en' | 'hi') => {
    setBusy(true);
    try {
      await downloadFile(`/exports/${kind}.xlsx`, { ...params, lang }, `${kind}.xlsx`);
    } catch (error) {
      notifyError(error);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Menu position="bottom-end" withinPortal>
      <Menu.Target>
        <Button
          variant="default"
          leftSection={<IconFileSpreadsheet size={18} />}
          disabled={disabled}
          loading={busy}
        >
          {t('reports.excel')}
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {(['en', 'hi'] as const).map((lang) => (
          <Menu.Item key={lang} onClick={() => void download(lang)}>
            {t(`lang.${lang}`)}
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
