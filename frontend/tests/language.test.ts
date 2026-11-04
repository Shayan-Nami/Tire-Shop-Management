import assert from 'node:assert/strict';
import { test, type TestContext } from 'node:test';
import { translations } from '../src/utils/i18n.ts';
import { mountComponent, nodes, text } from './componentHarness.ts';

type Harness = ReturnType<typeof mountComponent>;

function find(h: Harness, predicate: (node: any) => boolean) {
  const result = nodes(h.tree, predicate)[0];
  assert.ok(result, 'Expected control was not found');
  return result;
}

function mockDOMEnvironment(t: TestContext, initialStorage: Record<string, string> = {}) {
  const values = new Map<string, string>(Object.entries(initialStorage));
  const storage = {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
    clear: () => { values.clear(); },
  };

  const attrs = new Map<string, string>();
  const docElement = {
    getAttribute: (attr: string) => attrs.get(attr) ?? null,
    setAttribute: (attr: string, val: string) => { attrs.set(attr, val); },
    classList: {
      contains: () => false,
      add: () => {},
      remove: () => {},
    },
    lang: 'fa',
    dir: 'rtl',
  };

  const bodyAttrs = new Map<string, string>();
  const bodyElement = {
    getAttribute: (attr: string) => bodyAttrs.get(attr) ?? null,
    setAttribute: (attr: string, val: string) => { bodyAttrs.set(attr, val); },
    dir: 'rtl',
  };

  const doc = {
    documentElement: docElement,
    body: bodyElement,
    addEventListener: () => {},
    removeEventListener: () => {},
  };

  const location = { href: '/dashboard', search: '' };
  const win = {
    location,
    matchMedia: () => ({ matches: false }),
  };

  const descriptors = ['localStorage', 'window', 'document'].map((name) => [name, Object.getOwnPropertyDescriptor(globalThis, name)] as const);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: storage });
  Object.defineProperty(globalThis, 'window', { configurable: true, value: win });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: doc });

  t.after(() => {
    for (const [name, descriptor] of descriptors) {
      if (descriptor) Object.defineProperty(globalThis, name, descriptor);
      else Reflect.deleteProperty(globalThis, name);
    }
  });

  return { storage, attrs, bodyAttrs, docElement, bodyElement };
}

test('i18n translation dictionary covers core application terms in FA and EN', () => {
  assert.ok(translations.appTitle.fa && translations.appTitle.en);
  assert.ok(translations.appName.fa && translations.appName.en);
  assert.ok(translations.operationalMenu.fa && translations.operationalMenu.en);
  assert.ok(translations.navDashboard.fa && translations.navDashboard.en);
  assert.ok(translations.roleManager.fa && translations.roleManager.en);
  assert.ok(translations.roleTechnician.fa && translations.roleTechnician.en);
  assert.ok(translations.roleWarehouse.fa && translations.roleWarehouse.en);
  assert.equal(translations.langToggleAria.fa, 'تغییر زبان بین فارسی و انگلیسی (FA / EN)');
});

test('English interpolation preserves zero and inserts values without modifying saved text', (t) => {
  mockDOMEnvironment(t, { language: 'en' });
  const provider = mountComponent('../src/context/LanguageContext.tsx', 'LanguageProvider', {
    '../utils/i18n': { translations },
  }, { children: null });
  t.after(() => provider.unmount());
  const translate = provider.tree.props.value.t;
  assert.equal(translate('Missing key', 'Count: {count}', { count: 0 }), 'Count: 0');
  assert.equal(translate('Missing key', '{name}', { name: 'نام مشتری' }), 'نام مشتری');
});

test('LanguageProvider defaults to Persian (fa) with rtl direction when storage is empty', async (t) => {
  const env = mockDOMEnvironment(t);

  const provider = mountComponent('../src/context/LanguageContext.tsx', 'LanguageProvider', {
    '../utils/i18n': { translations },
  }, {
    children: null,
  });

  // Check state directly
  assert.ok(provider.tree.props.value);
  const ctx = provider.tree.props.value;
  assert.equal(ctx.language, 'fa');
  assert.equal(ctx.direction, 'rtl');
  assert.equal(ctx.isRTL, true);
  assert.equal(ctx.t('appName'), 'تایر منیجر');

  // Verify document was updated
  assert.equal(env.attrs.get('dir'), 'rtl');
  assert.equal(env.attrs.get('lang'), 'fa');
  assert.equal(env.storage.getItem('language'), 'fa');
});

test('LanguageProvider loads English from localStorage and applies ltr direction', async (t) => {
  const env = mockDOMEnvironment(t, { language: 'en' });

  const provider = mountComponent('../src/context/LanguageContext.tsx', 'LanguageProvider', {
    '../utils/i18n': { translations },
  }, {
    children: null,
  });

  const ctx = provider.tree.props.value;
  assert.equal(ctx.language, 'en');
  assert.equal(ctx.direction, 'ltr');
  assert.equal(ctx.isRTL, false);
  assert.equal(ctx.t('appName'), 'Tire Manager');
  assert.equal(env.attrs.get('dir'), 'ltr');
  assert.equal(env.attrs.get('lang'), 'en');
});

test('LanguageProvider toggles language between FA and EN and syncs localStorage & document attributes', async (t) => {
  const env = mockDOMEnvironment(t);

  const provider = mountComponent('../src/context/LanguageContext.tsx', 'LanguageProvider', {
    '../utils/i18n': { translations },
  }, {
    children: null,
  });

  assert.equal(provider.tree.props.value.language, 'fa');
  assert.equal(env.attrs.get('dir'), 'rtl');

  // Toggle to EN
  provider.tree.props.value.toggleLanguage();
  await provider.flush();

  assert.equal(provider.tree.props.value.language, 'en');
  assert.equal(provider.tree.props.value.direction, 'ltr');
  assert.equal(provider.tree.props.value.isRTL, false);
  assert.equal(env.storage.getItem('language'), 'en');
  assert.equal(env.attrs.get('dir'), 'ltr');
  assert.equal(env.attrs.get('lang'), 'en');
  assert.equal(provider.tree.props.value.t('navDashboard'), 'Dashboard');

  // Toggle back to FA
  provider.tree.props.value.toggleLanguage();
  await provider.flush();

  assert.equal(provider.tree.props.value.language, 'fa');
  assert.equal(provider.tree.props.value.direction, 'rtl');
  assert.equal(provider.tree.props.value.isRTL, true);
  assert.equal(env.storage.getItem('language'), 'fa');
  assert.equal(env.attrs.get('dir'), 'rtl');
  assert.equal(env.attrs.get('lang'), 'fa');
  assert.equal(provider.tree.props.value.t('navDashboard'), 'میز کار و داشبورد');
});

test('Navbar renders language toggle button and responds to click', async (t) => {
  mockDOMEnvironment(t);

  let currentLang = 'fa';
  const toggleLanguage = () => {
    currentLang = currentLang === 'fa' ? 'en' : 'fa';
  };

  const authContext = {
    user: { id: 1, username: 'testuser', role: 'MANAGER', full_name: 'مدیر تستی' },
    logout: async () => {},
    currencyUnit: 'toman',
    toggleCurrencyUnit: () => {},
  };

  const nav = mountComponent('../src/components/layout/Navbar.tsx', 'Navbar', {
    '../../context/AuthContext': { useAuth: () => authContext },
    '../../context/LanguageContext': {
      useLanguage: () => ({
        language: currentLang,
        direction: currentLang === 'fa' ? 'rtl' : 'ltr',
        isRTL: currentLang === 'fa',
        toggleLanguage,
        setLanguage: () => {},
        t: (k: string, d?: string) => translations[k]?.[currentLang as 'fa' | 'en'] || d || k,
      }),
    },
    'react-router-dom': { Link: ({ children, ...props }: any) => ({ type: 'a', props, children }) },
    '../auth/ProfileModal': { ProfileModal: () => null },
    '../auth/ChangePasswordModal': { ChangePasswordModal: () => null },
  });

  const langBtn = find(nav, (node) => node.type === 'button' && node.props?.['data-testid'] === 'language-toggle-btn');
  assert.ok(langBtn, 'Language toggle button should exist in Navbar');

  // Initial state is FA
  const btnContent = text(langBtn);
  assert.ok(btnContent.includes('FA'));

  // Click toggle
  langBtn.props.onClick({ preventDefault: () => {} });
  nav.render();

  assert.equal(currentLang, 'en', 'Language should switch to English on click');
});
