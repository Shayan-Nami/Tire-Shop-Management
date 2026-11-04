import { useLanguage } from '../context/LanguageContext';
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Plus,
  Trash2,
  User,
  Package,
  Wrench,
  CheckCircle2,
  FileText,
  AlertCircle,
  Search,
} from 'lucide-react';
import { catalogApi } from '../api/catalog';
import { crmApi } from '../api/crm';
import { servicesApi } from '../api/services';
import { invoicesApi } from '../api/invoices';
import { Customer, Vehicle, Tire, TechnicalService } from '../types';
import { IranianPlateBadge } from '../components/plates/IranianPlateBadge';
import { formatCurrency } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';
import { parseApiError } from '../utils/errorParser';
import { createRequestSequence, fetchAllPages, isCurrentInvoiceVehicle, invoiceSubmitLabel } from '../utils/invoiceRequests';

interface SelectedTireRow {
  tireId: number;
  tire: Tire;
  quantity: number;
  unitPrice: number;
}

interface SelectedServiceRow {
  serviceId: number;
  service: TechnicalService;
  quantity: number;
  unitPrice: number;
}

export const CreateInvoice: React.FC = () => {
  const { t, language } = useLanguage();
  const { currencyUnit } = useAuth();
  const navigate = useNavigate();

  // داده‌های پایه بارگذاری‌شده
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [customerVehicles, setCustomerVehicles] = useState<Vehicle[]>([]);
  const [tires, setTires] = useState<Tire[]>([]);
  const [services, setServices] = useState<TechnicalService[]>([]);

  // انتخاب‌ها
  const [selectedCustomerId, setSelectedCustomerId] = useState<number | ''>('');
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | ''>('');
  const [tireItems, setTireItems] = useState<SelectedTireRow[]>([]);
  const [serviceItems, setServiceItems] = useState<SelectedServiceRow[]>([]);

  // جستجوی زنده مشتری
  const [customerSearch, setCustomerSearch] = useState<string>('');
  const [isSearchingCustomer, setIsSearchingCustomer] = useState<boolean>(false);
  const [loadingVehicles, setLoadingVehicles] = useState<boolean>(false);

  // تخفیف و وضعیت
  const [discountAmount, setDiscountAmount] = useState<string>('0');
  const [discountPercent, setDiscountPercent] = useState<string>('0');
  const [status, setStatus] = useState<'CONFIRMED' | 'DRAFT'>('CONFIRMED');
  const [paymentStatus, setPaymentStatus] = useState<'UNPAID' | 'PAID'>('PAID');
  const [notes, setNotes] = useState<string>('');

  // وضعیت ایجاد مشتری و خودرو جدید
  const [showNewCustomerModal, setShowNewCustomerModal] = useState<boolean>(false);
  const [tempCreatedCustomer, setTempCreatedCustomer] = useState<Customer | null>(null);
  const [newCustomerName, setNewCustomerName] = useState<string>('');
  const [newCustomerPhone, setNewCustomerPhone] = useState<string>('');
  const [newCustomerNationalCode, setNewCustomerNationalCode] = useState<string>('');
  const [newVehiclePlate, setNewVehiclePlate] = useState<string>('');
  const [newVehicleModel, setNewVehicleModel] = useState<string>(t("پژو ۲۰۶"));

  // استیت‌های لودینگ و خطا
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [catalogError, setCatalogError] = useState<string | null>(null);
  const [customerError, setCustomerError] = useState<string | null>(null);
  const [vehicleError, setVehicleError] = useState<string | null>(null);
  const [quickCreateError, setQuickCreateError] = useState<string | null>(null);
  const [creatingCustomer, setCreatingCustomer] = useState(false);
  const vehicleRequests = useRef(createRequestSequence());
  const customerRequests = useRef(createRequestSequence());
  const quickCreateRequests = useRef(createRequestSequence());
  const quickCreateBusy = useRef(false);
  const submitBusy = useRef(false);
  const quickCreateDialog = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (showNewCustomerModal) quickCreateDialog.current?.showModal();
  }, [showNewCustomerModal]);
  const selectedCustomerIdRef = useRef<number | ''>('');
  const selectedVehicleIdRef = useRef<number | ''>('');

  useEffect(() => {
    const vehicles = vehicleRequests.current;
    const customers = customerRequests.current;
    const quickCreate = quickCreateRequests.current;
    return () => {
      vehicles.invalidate();
      customers.invalidate();
      quickCreate.invalidate();
    };
  }, []);

  const resetCustomerSelection = useCallback((custId: number | '') => {
    // Invalidate synchronously, before React commits the changed customer.
    vehicleRequests.current.invalidate();
    selectedCustomerIdRef.current = custId;
    setSelectedCustomerId(custId);
    selectedVehicleIdRef.current = '';
    setSelectedVehicleId('');
    setCustomerVehicles([]);
    setLoadingVehicles(false);
    setVehicleError(null);
  }, []);

  const loadVehiclesForCustomer = async (custId: number) => {
    const request = vehicleRequests.current.begin();
    const isCurrent = () => vehicleRequests.current.isCurrent(request)
      && selectedCustomerIdRef.current === custId;
    setLoadingVehicles(true);
    try {
      const vehicles = await fetchAllPages(
        (page) => crmApi.getVehicles({ customer: custId, page, page_size: 100 }),
        isCurrent,
      );
      if (!isCurrent()) return;
      const ownedVehicles = vehicles.filter((vehicle) => vehicle.customer === custId);
      setCustomerVehicles(ownedVehicles);
      selectedVehicleIdRef.current = ownedVehicles[0]?.vehicle_id ?? '';
      setSelectedVehicleId(selectedVehicleIdRef.current);
    } catch (error) {
      if (isCurrent()) setVehicleError(parseApiError(error, t("خطا در دریافت خودروهای مشتری"), language));
    } finally {
      if (isCurrent()) setLoadingVehicles(false);
    }
  };

  useEffect(() => {
    let active = true;
    const fetchData = async () => {
      try {
        const [allTires, allServices] = await Promise.all([
          fetchAllPages((page) => catalogApi.getTires({ page, page_size: 100 }), () => active),
          fetchAllPages((page) => servicesApi.getServices({ page, page_size: 100 }), () => active),
        ]);
        if (!active) return;
        setTires(allTires);
        setServices(allServices);
      } catch (error) {
        if (active) setCatalogError(parseApiError(error, t("خطا در بارگذاری کالاها و خدمات"), language));
      }
    };
    void fetchData();
    return () => { active = false; };
  }, [t, language]);

  useEffect(() => {
    const requests = customerRequests.current;
    const request = requests.begin();
    const isCurrent = () => requests.isCurrent(request);
    const timer = setTimeout(async () => {
      setIsSearchingCustomer(true);
      setCustomerError(null);
      try {
        const found = await fetchAllPages(
          (page) => crmApi.getCustomers({ search: customerSearch.trim() || undefined, page, page_size: 100 }),
          isCurrent,
        );
        if (!isCurrent()) return;
        setCustomers((previous) => {
          const selected = previous.find((customer) => customer.customer_id === selectedCustomerIdRef.current);
          return selected && !found.some((customer) => customer.customer_id === selected.customer_id)
            ? [selected, ...found] : found;
        });
      } catch (error) {
        if (isCurrent()) setCustomerError(parseApiError(error, t("خطا در جستجوی مشتریان"), language));
      } finally {
        if (isCurrent()) setIsSearchingCustomer(false);
      }
    }, 350);
    return () => {
      clearTimeout(timer);
      requests.invalidate();
    };
  }, [customerSearch, t, language]);

  const handleCustomerChange = (custId: number | '') => {
    quickCreateRequests.current.invalidate();
    quickCreateBusy.current = false;
    setCreatingCustomer(false);
    resetCustomerSelection(custId);
    if (custId) void loadVehiclesForCustomer(custId);
  };

  const closeQuickCreate = () => {
    quickCreateDialog.current?.close();
    quickCreateRequests.current.invalidate();
    quickCreateBusy.current = false;
    setCreatingCustomer(false);
    setShowNewCustomerModal(false);
    setQuickCreateError(null);
    setTempCreatedCustomer(null);
    setNewCustomerName('');
    setNewCustomerPhone('');
    setNewCustomerNationalCode('');
    setNewVehiclePlate('');
  };

  // افزودن سطر تایر
  const addTireItem = (tireId: number) => {
    const tire = tires.find((t) => t.tire_id === tireId);
    if (!tire) return;

    if (tire.stock_quantity <= 0) {
      alert(t("موجودی تایر '{0}' در انبار صفر است.", undefined, { 0: tire.tire_name }));
      return;
    }

    const existing = tireItems.find((item) => item.tireId === tireId);
    if (existing) {
      if (existing.quantity >= tire.stock_quantity) {
        alert(t("تعداد درخواستی نمی‌تواند بیشتر از موجودی انبار ({0}) باشد.", undefined, { 0: tire.stock_quantity }));
        return;
      }
      setTireItems(
        tireItems.map((item) =>
          item.tireId === tireId ? { ...item, quantity: item.quantity + 1 } : item
        )
      );
    } else {
      setTireItems([
        ...tireItems,
        {
          tireId: tire.tire_id,
          tire,
          quantity: 1,
          unitPrice: parseFloat(String(tire.sale_price)) || 0,
        },
      ]);
    }
  };

  const updateTireItemQty = (tireId: number, qty: number) => {
    const tire = tires.find((t) => t.tire_id === tireId);
    if (!tire) return;

    if (qty > tire.stock_quantity) {
      alert(t("حداکثر موجودی قابل فروش این تایر {0} حلقه است.", undefined, { 0: tire.stock_quantity }));
      qty = tire.stock_quantity;
    }

    if (qty <= 0) {
      removeTireItem(tireId);
      return;
    }

    setTireItems(
      tireItems.map((item) =>
        item.tireId === tireId ? { ...item, quantity: qty } : item
      )
    );
  };

  const updateTireItemUnitPrice = (tireId: number, price: number) => {
    if (price < 0 || isNaN(price)) price = 0;
    setTireItems(
      tireItems.map((item) =>
        item.tireId === tireId ? { ...item, unitPrice: price } : item
      )
    );
  };

  const removeTireItem = (tireId: number) => {
    setTireItems(tireItems.filter((item) => item.tireId !== tireId));
  };

  // افزودن سطر خدمات فنی
  const addServiceItem = (serviceId: number) => {
    const service = services.find((s) => s.service_id === serviceId);
    if (!service) return;

    const existing = serviceItems.find((item) => item.serviceId === serviceId);
    if (existing) {
      setServiceItems(
        serviceItems.map((item) =>
          item.serviceId === serviceId ? { ...item, quantity: item.quantity + 1 } : item
        )
      );
    } else {
      setServiceItems([
        ...serviceItems,
        {
          serviceId: service.service_id,
          service,
          quantity: 1,
          unitPrice: parseFloat(String(service.price)) || 0,
        },
      ]);
    }
  };

  const updateServiceItemQty = (serviceId: number, qty: number) => {
    if (qty <= 0) {
      removeServiceItem(serviceId);
      return;
    }
    setServiceItems(
      serviceItems.map((item) =>
        item.serviceId === serviceId ? { ...item, quantity: qty } : item
      )
    );
  };

  const updateServiceItemUnitPrice = (serviceId: number, price: number) => {
    if (price < 0 || isNaN(price)) price = 0;
    setServiceItems(
      serviceItems.map((item) =>
        item.serviceId === serviceId ? { ...item, unitPrice: price } : item
      )
    );
  };

  const removeServiceItem = (serviceId: number) => {
    setServiceItems(serviceItems.filter((item) => item.serviceId !== serviceId));
  };

  // ثبت سریع مشتری و خودروی جدید
  const handleCreateCustomerAndVehicle = async (e: React.FormEvent) => {
    e.preventDefault();
    if (quickCreateBusy.current || submitBusy.current) return;
    if (!newCustomerName.trim() || !newCustomerPhone.trim() || !newVehiclePlate.trim()) {
      setQuickCreateError(t("لطفاً نام، شماره موبایل و شماره پلاک را تکمیل فرمایید."));
      return;
    }

    const request = quickCreateRequests.current.begin();
    const isCurrent = () => quickCreateRequests.current.isCurrent(request);
    quickCreateBusy.current = true;
    setCreatingCustomer(true);
    setQuickCreateError(null);
    // A prior customer's vehicle request must not overwrite quick creation.
    resetCustomerSelection(selectedCustomerIdRef.current);
    let customerToUse = tempCreatedCustomer;
    try {
      if (!customerToUse) {
        customerToUse = await crmApi.createCustomer({
          full_name: newCustomerName.trim(),
          phone_number: newCustomerPhone.trim(),
          national_code: newCustomerNationalCode.trim() || undefined,
        });
        if (!isCurrent()) return;
        setTempCreatedCustomer(customerToUse);
        const created = customerToUse;
        setCustomers((previous) => [created, ...previous.filter((customer) => customer.customer_id !== created.customer_id)]);
      }
      if (!isCurrent()) return;
      const customerId = customerToUse.customer_id;
      resetCustomerSelection(customerId);
      const vehicles = await fetchAllPages(
        (page) => crmApi.getVehicles({ customer: customerId, page, page_size: 100 }),
        isCurrent,
      );
      if (!isCurrent()) return;
      const newVehicle = await crmApi.createVehicle({
        customer: customerToUse.customer_id,
        license_plate: newVehiclePlate.trim(),
        model: newVehicleModel.trim(),
      });
      if (!isCurrent()) return;
      if (newVehicle.customer !== selectedCustomerIdRef.current) {
        throw new Error(t("خودروی دریافتی متعلق به مشتری انتخاب‌شده نیست."));
      }

      setCustomerVehicles([newVehicle, ...vehicles.filter((vehicle) => vehicle.customer === newVehicle.customer && vehicle.vehicle_id !== newVehicle.vehicle_id)]);
      selectedVehicleIdRef.current = newVehicle.vehicle_id;
      setSelectedVehicleId(newVehicle.vehicle_id);
      closeQuickCreate();
    } catch (error) {
      if (isCurrent()) setQuickCreateError(parseApiError(error, t("خطا در ثبت مشتری یا خودرو؛ اطلاعات ذخیره‌شده را پیش از تلاش مجدد بررسی کنید."), language));
    } finally {
      if (isCurrent()) {
        quickCreateBusy.current = false;
        setCreatingCustomer(false);
      }
    }
  };

  // محاسبات مالی
  const tiresSubtotal = tireItems.reduce(
    (acc, curr) => acc + curr.quantity * curr.unitPrice,
    0
  );
  const servicesSubtotal = serviceItems.reduce(
    (acc, curr) => acc + curr.quantity * curr.unitPrice,
    0
  );
  const grossTotal = tiresSubtotal + servicesSubtotal;

  const numDiscountAmount = parseFloat(discountAmount) || 0;
  const numDiscountPercent = parseFloat(discountPercent) || 0;

  let calculatedDiscount = 0;
  if (numDiscountPercent > 0) {
    calculatedDiscount = (grossTotal * numDiscountPercent) / 100;
  } else {
    calculatedDiscount = numDiscountAmount;
  }

  const netPayable = Math.max(0, grossTotal - calculatedDiscount);

  // ثبت نهایی فاکتور
  const vehicleIsCurrent = isCurrentInvoiceVehicle(selectedCustomerId, selectedVehicleId, customerVehicles, loadingVehicles);

  const handleSubmitInvoice = async () => {
    if (submitBusy.current) return;
    if (quickCreateBusy.current || creatingCustomer || loadingVehicles || selectedCustomerIdRef.current !== selectedCustomerId) {
      setErrorMessage(t("لطفاً تا تکمیل اطلاعات مشتری و خودرو صبر کنید."));
      return;
    }
    if (!selectedCustomerId) {
      setErrorMessage(t("لطفاً مشتری را انتخاب فرمایید."));
      return;
    }
    if (!vehicleIsCurrent || selectedVehicleIdRef.current !== selectedVehicleId) {
      setErrorMessage(t("لطفاً خودروی مربوطه را انتخاب فرمایید."));
      return;
    }
    if (tireItems.length === 0 && serviceItems.length === 0) {
      setErrorMessage(t("حداقل یک حلقه لاستیک یا یک خدمت فنی باید به فاکتور افزوده شود."));
      return;
    }

    submitBusy.current = true;
    setSubmitting(true);
    setErrorMessage(null);

    try {
      await invoicesApi.createSalesInvoice({
        customer: Number(selectedCustomerId),
        vehicle: Number(selectedVehicleId),
        tire_items: tireItems.map((item) => ({
          tire: item.tireId,
          quantity: item.quantity,
          unit_price: item.unitPrice,
        })),
        service_items: serviceItems.map((item) => ({
          service: item.serviceId,
          quantity: item.quantity,
          unit_price: item.unitPrice,
        })),
        discount_amount: numDiscountPercent > 0 ? 0 : numDiscountAmount,
        discount_percent: numDiscountPercent,
        status,
        payment_status: paymentStatus,
        notes: notes.trim() || undefined,
      });

      navigate('/invoices/sales');
    } catch (error) {
      setErrorMessage(parseApiError(error, t("خطا در ثبت فاکتور فروش"), language));
    } finally {
      submitBusy.current = false;
      setSubmitting(false);
    }
  };

  return (
    <div className="page-stack">
      {/* سربرگ */}
      <div className="page-heading">
        <div>
          <h1 className="text-xl md:text-2xl font-black text-slate-900 dark:text-white">{t("میز کار صندوق و صدور فاکتور فروش")}</h1>
          <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{t("ثبت آنی فروش کالا، تعویض، بالانس و صدور صورتحساب هوشمند")}</p>
        </div>
      </div>

      {errorMessage && (
        <div role="alert" className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-600 dark:text-rose-400 text-xs flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {(catalogError || customerError || vehicleError) && (
        <div role="alert" className="p-4 rounded-xl bg-rose-500/10 text-rose-700 dark:text-rose-300 text-xs space-y-1">
          {catalogError && <p>{catalogError} {t("— برای تلاش مجدد صفحه را تازه‌سازی کنید.")}</p>}
          {customerError && <p id="invoice-customer-error">{customerError} {t("— برای تلاش مجدد جستجو را تغییر دهید.")}</p>}
          {vehicleError && <p id="invoice-vehicle-error">{vehicleError} {t("— برای تلاش مجدد مشتری را دوباره انتخاب کنید.")}</p>}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ستون ۲تایی راست: فرم اقلام، مشتری و خدمات */}
        <div className="lg:col-span-2 space-y-6">
          {/* کارت انتخاب مشتری و خودرو */}
          <div className="p-5 surface-panel space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100 font-bold text-sm">
                <User className="w-4 h-4 text-brand-600" />
                <span>{t("مشخصات مشتری و خودرو")}</span>
              </div>
              <button
                type="button"
                onClick={() => setShowNewCustomerModal(true)}
                                disabled={submitting}
                className="text-xs text-brand-600 dark:text-brand-400 hover:underline flex items-center gap-1 font-semibold"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>{t("ثبت سریع مشتری/خودرو جدید")}</span>
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* انتخاب مشتری با جستجوی زنده */}
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <label htmlFor="invoice-customer" className="font-semibold text-slate-700 dark:text-slate-300 block">{t("مشتری:")}</label>
                  {isSearchingCustomer && (
                    <span className="text-[10px] text-brand-600 dark:text-brand-400 animate-pulse font-medium">{t("در حال جستجو...")}</span>
                  )}
                </div>
                <div className="relative">
                  <input
                    type="text"
                    aria-label={t("جستجوی نام یا موبایل مشتری")}
                    value={customerSearch}
                    onChange={(e) => {
                      customerRequests.current.invalidate();
                      setCustomerSearch(e.target.value);
                    }}
                    placeholder={t("جستجوی زنده نام یا موبایل مشتری...")}
                    className="ui-field w-full pe-3 ps-8 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-xs focus:ring-2 focus:ring-brand-500 outline-none mb-1.5"
                  />
                  <Search className="w-3.5 h-3.5 text-slate-400 absolute top-2.5 start-2.5" />
                </div>
                <select
                  id="invoice-customer"
                  aria-busy={isSearchingCustomer}
                  aria-describedby={customerError ? 'invoice-customer-error' : undefined}
                  disabled={submitting}
                  value={selectedCustomerId}
                  onChange={(e) => handleCustomerChange(e.target.value ? Number(e.target.value) : '')}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none"
                >
                  <option value="">{t("انتخاب خریدار (")}{customers.length} {' '}{t("مورد)...")}</option>
                  {customers.map((c) => (
                    <option key={c.customer_id} value={c.customer_id}>
                      {c.full_name} ({c.phone_number})
                    </option>
                  ))}
                </select>
              </div>

              {/* انتخاب خودرو */}
              <div className="space-y-1.5 text-xs">
                <div className="flex items-center justify-between">
                  <label htmlFor="invoice-vehicle" className="font-semibold text-slate-700 dark:text-slate-300 block">{t("خودرو و پلاک:")}</label>
                  {loadingVehicles && (
                    <span className="text-[10px] text-brand-600 dark:text-brand-400 animate-pulse font-medium">{t("در حال دریافت خودروها...")}</span>
                  )}
                </div>
                <select
                  id="invoice-vehicle"
                  aria-busy={loadingVehicles}
                  aria-describedby={vehicleError ? 'invoice-vehicle-error' : undefined}
                  value={selectedVehicleId}
                  onChange={(e) => {
                                      selectedVehicleIdRef.current = e.target.value ? Number(e.target.value) : '';
                                      setSelectedVehicleId(selectedVehicleIdRef.current);
                                    }}
                  disabled={submitting || creatingCustomer || !selectedCustomerId || customerVehicles.length === 0 || loadingVehicles}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none disabled:opacity-50 mt-7 sm:mt-8"
                >
                  {vehicleError ? (
                    <option value="">{t("دریافت خودروها ناموفق بود؛ مشتری را دوباره انتخاب کنید")}</option>
                  ) : loadingVehicles ? (
                    <option value="">{t("در حال بارگذاری خودروهای مشتری...")}</option>
                  ) : customerVehicles.length === 0 ? (
                    <option value="">{t("هیچ خودرویی برای این مشتری ثبت نشده است")}</option>
                  ) : (
                    customerVehicles.map((v) => (
                      <option key={v.vehicle_id} value={v.vehicle_id}>
                        {v.model} - {v.license_plate}
                      </option>
                    ))
                  )}
                </select>
              </div>
            </div>

            {/* پیش‌نمایش گرافیکی پلاک انتخاب‌شده */}
            {selectedVehicleId && (
              <div className="pt-2 flex items-center gap-3">
                <span className="text-xs text-slate-500">{t("پلاک انتخاب‌شده:")}</span>
                <IranianPlateBadge
                  plateString={
                    customerVehicles.find((v) => v.vehicle_id === selectedVehicleId)
                      ?.license_plate
                  }
                  size="sm"
                />
              </div>
            )}
          </div>

          {/* انتخاب و اقلام تایر */}
          <div className="p-5 surface-panel space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100 font-bold text-sm">
                <Package className="w-4 h-4 text-brand-600" />
                <span>{t("اقلام تایر و لاستیک")}</span>
              </div>
              <div className="w-56 text-xs">
                <select
                  aria-label={t("افزودن تایر از کاتالوگ")}
                  onChange={(e) => {
                    if (e.target.value) {
                      addTireItem(Number(e.target.value));
                      e.target.value = '';
                    }
                  }}
                  className="ui-field w-full px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs"
                >
                  <option value="">{t("+ افزودن تایر از کاتالوگ...")}</option>
                  {tires.map((tireChoice) => (
                    <option
                      key={tireChoice.tire_id}
                      value={tireChoice.tire_id}
                      disabled={tireChoice.stock_quantity <= 0}
                    >
                      {tireChoice.tire_name} ({tireChoice.brand_name}{t(") - موجودی:")} {tireChoice.stock_quantity}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* پیام راهنمای نرخ‌گذاری بر اساس تورم و بازار */}
            <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-xl text-amber-700 dark:text-amber-300 text-[11px] flex items-center gap-2">
              <span className="font-bold shrink-0">{t("💡 نرخ‌گذاری شناور بازار:")}</span>
              <span>{t("قیمت واحد تایرها بر اساس نوسانات بازار و تورم قابل تعیین است؛ نرخ کاتالوگ صرفاً به عنوان پیشنهاد پیش‌فرض درج می‌شود و می‌توانید آن را در ستون «قیمت واحد فروش» مستقیماً تغییر دهید.")}</span>
            </div>

            {tireItems.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">{t("هیچ تایری به فاکتور افزوده نشده است. از منوی بالا تایر را انتخاب فرمایید.")}</div>
            ) : (
              <div className="table-scroll overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="data-table w-full text-xs text-start">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">{t("شرح تایر")}</th>
                      <th className="py-2.5 px-3 text-center">{t("موجودی")}</th>
                      <th className="py-2.5 px-3 text-center">{t("تعداد (حلقه)")}</th>
                      <th className="py-2.5 px-3">{t("قیمت واحد فروش (نرخ روز بازار)")}</th>
                      <th className="py-2.5 px-3">{t("جمع")}</th>
                      <th className="py-2.5 px-3 text-center">{t("حذف")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {tireItems.map((item) => (
                      <tr key={item.tireId}>
                        <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                          <bdi dir="auto">{item.tire.tire_name}</bdi>
                          <span className="block text-[10px] text-slate-400 font-normal">
                            <bdi dir="auto">{item.tire.brand_name}</bdi> - <bdi dir="auto">{item.tire.size_name}</bdi>
                          </span>
                        </td>
                        <td className="py-2.5 px-3 text-center text-slate-500 tabular-nums">
                          {item.tire.stock_quantity}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <input
                            type="number"
                            min={1}
                            max={item.tire.stock_quantity}
                            value={item.quantity}
                            onChange={(e) =>
                              updateTireItemQty(item.tireId, parseInt(e.target.value) || 0)
                            }
                            className="ui-field w-16 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-center font-bold text-xs"
                          />
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min={0}
                                step={10000}
                                value={item.unitPrice}
                                onChange={(e) =>
                                  updateTireItemUnitPrice(
                                    item.tireId,
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                                className="ui-field w-28 sm:w-32 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-end font-bold text-xs tabular-nums focus:ring-2 focus:ring-brand-500 outline-none"
                              />
                              <span className="text-[10px] text-slate-400 font-medium">{t("ریال")}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              <span>{t("پایه:")} {formatCurrency(item.tire.sale_price, true, currencyUnit, language)}</span>
                              {item.unitPrice !== Number(item.tire.sale_price) && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateTireItemUnitPrice(item.tireId, Number(item.tire.sale_price))
                                  }
                                  className="text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                                  title={t("بازنشانی به نرخ کاتالوگ")}
                                >{t("بازنشانی")}</button>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 font-bold tabular-nums">
                          {formatCurrency(item.quantity * item.unitPrice, true, currencyUnit, language)}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            type="button"
                            onClick={() => removeTireItem(item.tireId)}
                            className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* انتخاب و اقلام خدمات کارگاهی */}
          <div className="p-5 surface-panel space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-slate-800 dark:text-slate-100 font-bold text-sm">
                <Wrench className="w-4 h-4 text-brand-600" />
                <span>{t("خدمات فنی خودرو (تعویض، بالانس، پنچرگیری)")}</span>
              </div>
              <div className="w-56 text-xs">
                <select
                  aria-label={t("افزودن خدمت کارگاهی")}
                  onChange={(e) => {
                    if (e.target.value) {
                      addServiceItem(Number(e.target.value));
                      e.target.value = '';
                    }
                  }}
                  className="ui-field w-full px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs"
                >
                  <option value="">{t("+ افزودن خدمت کارگاهی...")}</option>
                  {services.map((s) => (
                    <option key={s.service_id} value={s.service_id}>
                      {s.service_name} ({formatCurrency(s.price, true, currencyUnit, language)})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {serviceItems.length === 0 ? (
              <div className="py-6 text-center text-xs text-slate-400 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">{t("هیچ خدمتی به فاکتور افزوده نشده است (اختیاری).")}</div>
            ) : (
              <div className="table-scroll overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-800">
                <table className="data-table w-full text-xs text-start">
                  <thead className="bg-slate-50 dark:bg-slate-800/60 text-slate-500 border-b border-slate-200 dark:border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">{t("عنوان خدمت")}</th>
                      <th className="py-2.5 px-3 text-center">{t("تعداد / چرخ")}</th>
                      <th className="py-2.5 px-3">{t("تعرفه واحد (ریال)")}</th>
                      <th className="py-2.5 px-3">{t("جمع")}</th>
                      <th className="py-2.5 px-3 text-center">{t("حذف")}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                    {serviceItems.map((item) => (
                      <tr key={item.serviceId}>
                        <td className="py-2.5 px-3 font-semibold text-slate-800 dark:text-slate-200">
                          <bdi dir="auto">{item.service.service_name}</bdi>
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <input
                            type="number"
                            min={1}
                            value={item.quantity}
                            onChange={(e) =>
                              updateServiceItemQty(item.serviceId, parseInt(e.target.value) || 0)
                            }
                            className="ui-field w-16 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-center font-bold text-xs"
                          />
                        </td>
                        <td className="py-2.5 px-3">
                          <div className="space-y-1">
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min={0}
                                step={10000}
                                value={item.unitPrice}
                                onChange={(e) =>
                                  updateServiceItemUnitPrice(
                                    item.serviceId,
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                                className="ui-field w-28 sm:w-32 px-2 py-1 bg-white dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-end font-bold text-xs tabular-nums focus:ring-2 focus:ring-brand-500 outline-none"
                              />
                              <span className="text-[10px] text-slate-400 font-medium">{t("ریال")}</span>
                            </div>
                            <div className="flex items-center gap-2 text-[10px] text-slate-400">
                              <span>{t("پایه:")} {formatCurrency(item.service.price, true, currencyUnit, language)}</span>
                              {item.unitPrice !== Number(item.service.price) && (
                                <button
                                  type="button"
                                  onClick={() =>
                                    updateServiceItemUnitPrice(item.serviceId, Number(item.service.price))
                                  }
                                  className="text-brand-600 dark:text-brand-400 hover:underline font-semibold"
                                  title={t("بازنشانی به تعرفه پایه")}
                                >{t("بازنشانی")}</button>
                              )}
                            </div>
                          </div>
                        </td>
                        <td className="py-2.5 px-3 font-bold tabular-nums">
                          {formatCurrency(item.quantity * item.unitPrice, true, currencyUnit, language)}
                        </td>
                        <td className="py-2.5 px-3 text-center">
                          <button
                            type="button"
                            onClick={() => removeServiceItem(item.serviceId)}
                            className="p-1 text-slate-400 hover:text-rose-600 transition-colors"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        {/* ستون ۱تایی چپ: خلاصه مالی، تخفیف، وضعیت و صدور */}
        <div className="space-y-6">
          <div className="p-5 surface-panel space-y-4">
            <h2 className="font-bold text-slate-900 dark:text-white text-sm">{t("صورتحساب و شرایط تسویه")}</h2>

            {/* ریز مبالغ */}
            <div className="space-y-2 text-xs border-b border-slate-100 dark:border-slate-800 pb-3">
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>{t("جمع اقلام تایر:")}</span>
                <span className="font-semibold tabular-nums">
                  {formatCurrency(tiresSubtotal, true, currencyUnit, language)}
                </span>
              </div>
              <div className="flex justify-between text-slate-600 dark:text-slate-400">
                <span>{t("جمع خدمات کارگاهی:")}</span>
                <span className="font-semibold tabular-nums">
                  {formatCurrency(servicesSubtotal, true, currencyUnit, language)}
                </span>
              </div>
              <div className="flex justify-between text-slate-800 dark:text-slate-200 font-bold pt-1">
                <span>{t("جمع ناخالص کل:")}</span>
                <span className="tabular-nums">
                  {formatCurrency(grossTotal, true, currencyUnit, language)}
                </span>
              </div>
            </div>

            {/* تخفیف */}
            <div className="space-y-2 text-xs">
              <label className="font-semibold text-slate-700 dark:text-slate-300 block">{t("تخفیف فاکتور:")}</label>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <span className="text-[10px] text-slate-400 block mb-1">{t("مبلغ ریالی:")}</span>
                  <input
                    type="number"
                    min={0}
                    aria-label={t("مبلغ تخفیف (ریال)")}
                    value={discountAmount}
                    onChange={(e) => {
                      setDiscountAmount(e.target.value);
                      setDiscountPercent('0');
                    }}
                    className="ui-field w-full px-2 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs"
                  />
                </div>
                <div>
                  <span className="text-[10px] text-slate-400 block mb-1">{t("درصدی (%):")}</span>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    aria-label={t("درصد تخفیف")}
                    value={discountPercent}
                    onChange={(e) => {
                      setDiscountPercent(e.target.value);
                      setDiscountAmount('0');
                    }}
                    className="ui-field w-full px-2 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-lg text-xs"
                  />
                </div>
              </div>
            </div>

            {/* مبلغ خالص قابل پرداخت */}
            <div className="p-3 rounded-xl bg-brand-50 dark:bg-brand-950/30 border border-brand-200 dark:border-brand-900/40 text-center space-y-1">
              <span className="text-xs text-brand-700 dark:text-brand-300 font-medium">{t("مبلغ نهایی قابل پرداخت:")}</span>
              <div className="text-xl font-black text-brand-600 dark:text-brand-400 tabular-nums">
                {formatCurrency(netPayable, true, currencyUnit, language)}
              </div>
            </div>

            {/* وضعیت صدور فاکتور */}
            <div className="space-y-2 text-xs">
              <label className="font-semibold text-slate-700 dark:text-slate-300 block">{t("وضعیت فاکتور:")}</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setStatus('CONFIRMED')}
                  aria-pressed={status === 'CONFIRMED'}
                  className={`py-2 px-3 rounded-xl font-bold transition-all text-xs flex items-center justify-center gap-1.5 ${
                    status === 'CONFIRMED'
                      ? 'bg-emerald-600 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>{t("تایید قطعی (کسر انبار)")}</span>
                </button>
                <button
                  type="button"
                  onClick={() => setStatus('DRAFT')}
                  aria-pressed={status === 'DRAFT'}
                  className={`py-2 px-3 rounded-xl font-bold transition-all text-xs flex items-center justify-center gap-1.5 ${
                    status === 'DRAFT'
                      ? 'bg-amber-600 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}
                >
                  <FileText className="w-3.5 h-3.5" />
                  <span>{t("پیش‌نویس")}</span>
                </button>
              </div>
            </div>

            {/* وضعیت پرداخت */}
            <div className="space-y-2 text-xs">
              <label className="font-semibold text-slate-700 dark:text-slate-300 block">{t("وضعیت تسویه اولیه:")}</label>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setPaymentStatus('PAID')}
                  className={`py-2 px-3 rounded-xl font-bold transition-all text-xs ${
                    paymentStatus === 'PAID'
                      ? 'bg-blue-600 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}
                >{t("تسویه کامل نقدی/پوز")}</button>
                <button
                  type="button"
                  onClick={() => setPaymentStatus('UNPAID')}
                  className={`py-2 px-3 rounded-xl font-bold transition-all text-xs ${
                    paymentStatus === 'UNPAID'
                      ? 'bg-slate-700 text-white shadow-sm'
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300'
                  }`}
                >{t("نسیه / تسویه بعداً")}</button>
              </div>
            </div>

            {/* یادداشت */}
            <div className="space-y-1.5 text-xs">
              <label className="font-semibold text-slate-700 dark:text-slate-300 block">{t("توضیحات فاکتور:")}</label>
              <textarea
                rows={2}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("یادداشت تکنسین...")}
                className="ui-field w-full px-3 py-1.5 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl focus:ring-2 focus:ring-brand-500 outline-none"
              />
            </div>

            <p id="invoice-submit-help" role="status" className="text-xs text-slate-500 dark:text-slate-400">
              {creatingCustomer ? t("ثبت مشتری و خودرو در حال انجام است.") : loadingVehicles ? t("منتظر دریافت خودروهای مشتری باشید.") : !vehicleIsCurrent ? t("برای ثبت فاکتور، مشتری و خودروی متعلق به او را انتخاب کنید.") : status === 'DRAFT' ? t("پیش‌نویس ذخیره می‌شود؛ موجودی انبار کسر نمی‌شود.") : t("فاکتور قطعی صادر و موجودی انبار کسر می‌شود.")}
            </p>
            {/* دکمه ثبت نهایی */}
            <button
              type="button"
              onClick={handleSubmitInvoice}
              disabled={submitting || creatingCustomer || !vehicleIsCurrent}
              aria-describedby="invoice-submit-help"
              className="action-primary w-full py-3 px-4 bg-brand-600 hover:bg-brand-700 text-white font-bold rounded-xl shadow-lg shadow-brand-600/30 flex items-center justify-center gap-2 text-sm transition-all duration-200 active:scale-[0.98] disabled:opacity-50"
            >
              <CheckCircle2 className="w-4 h-4" />
              <span>{t(invoiceSubmitLabel(status, submitting))}</span>
            </button>
          </div>
        </div>
      </div>

      {/* مدال ثبت سریع مشتری و خودرو جدید */}
      {showNewCustomerModal && (
        <dialog
          ref={quickCreateDialog}
          aria-labelledby="quick-create-title"
          onCancel={(event) => { event.preventDefault(); closeQuickCreate(); }}
          className="m-auto p-4 w-full max-w-lg max-h-[90dvh] overflow-y-auto bg-transparent backdrop:bg-slate-900/60 backdrop:backdrop-blur-sm"
        >
          <div className="bg-white dark:bg-slate-900 modal-card rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-800 max-w-md w-full overflow-hidden">
            <div className="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-850">
              <h2 id="quick-create-title" className="text-base font-bold text-slate-800 dark:text-slate-100">{t("ثبت مشتری و خودروی جدید")}</h2>
              <button
                type="button"
                onClick={closeQuickCreate}
                aria-label={t("بستن ثبت سریع")}
                className="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg"
              >
                ×
              </button>
            </div>

            <form onSubmit={handleCreateCustomerAndVehicle} aria-busy={creatingCustomer} className="p-6 space-y-4 text-xs">
              {quickCreateError && <p id="quick-create-error" role="alert" className="text-rose-600 dark:text-rose-400">{quickCreateError}</p>}
              {creatingCustomer && <p role="status">{t("در حال ثبت؛ بستن پنجره عملیات ذخیره‌سازی در سرور را لغو نمی‌کند.")}</p>}
              {tempCreatedCustomer && (
                <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-300 rounded-xl text-xs space-y-1">
                  <p className="font-bold">{t("✓ مشخصات مشتری «")}<bdi dir="auto">{tempCreatedCustomer.full_name}</bdi>{t("» با موفقیت ذخیره شد.")}</p>
                  <p className="text-[11px]">{t("اکنون اطلاعات خودرو و پلاک را اصلاح و دکمه «ثبت و انتخاب» را کلیک فرمایید.")}</p>
                </div>
              )}

              <div className="space-y-1.5">
                <label htmlFor="quick-customer-name" className="font-bold text-slate-700 dark:text-slate-300 block">{t("نام و نام خانوادگی مشتری:")}</label>
                <input
                  type="text"
                  required
                  disabled={!!tempCreatedCustomer}
                  id="quick-customer-name"
                  autoFocus
                  value={newCustomerName}
                  onChange={(e) => setNewCustomerName(e.target.value)}
                  placeholder={t("مثلاً: محمد حسینی")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl disabled:opacity-60"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="quick-customer-phone" className="font-bold text-slate-700 dark:text-slate-300 block">{t("شماره موبایل:")}</label>
                <input
                  type="text"
                  required
                  disabled={!!tempCreatedCustomer}
                  id="quick-customer-phone"
                  value={newCustomerPhone}
                  onChange={(e) => setNewCustomerPhone(e.target.value)}
                  placeholder="09123456789"
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end disabled:opacity-60"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="quick-customer-national-code" className="font-bold text-slate-700 dark:text-slate-300 block">{t("کد ملی (اختیاری):")}</label>
                <input
                  type="text"
                  disabled={!!tempCreatedCustomer}
                  id="quick-customer-national-code"
                  value={newCustomerNationalCode}
                  onChange={(e) => setNewCustomerNationalCode(e.target.value)}
                  placeholder="0012345678"
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end disabled:opacity-60"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="quick-vehicle-model" className="font-bold text-slate-700 dark:text-slate-300 block">{t("مدل خودرو:")}</label>
                <input
                  type="text"
                  required
                  id="quick-vehicle-model"
                  value={newVehicleModel}
                  onChange={(e) => setNewVehicleModel(e.target.value)}
                  placeholder={t("مثلاً: پژو پارس، سمند، دنا...")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="quick-vehicle-plate" className="font-bold text-slate-700 dark:text-slate-300 block">{t("شماره پلاک ایران (فرمت استاندارد: 12ب345-ایران11):")}</label>
                <input
                  type="text"
                  required
                  id="quick-vehicle-plate"
                  value={newVehiclePlate}
                  onChange={(e) => setNewVehiclePlate(e.target.value)}
                  placeholder={t("مثلاً: 34د567-ایران22")}
                  className="ui-field w-full px-3 py-2 bg-slate-50 dark:bg-slate-800 border border-slate-300 dark:border-slate-700 rounded-xl text-end font-mono"
                />
                <div className="pt-1">
                  <IranianPlateBadge plateString={newVehiclePlate} size="sm" />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={closeQuickCreate}
                  className="px-4 py-2 border border-slate-300 dark:border-slate-700 rounded-xl font-semibold text-slate-600 dark:text-slate-300"
                >{t("انصراف")}</button>
                <button
                  type="submit"
                  disabled={creatingCustomer}
                  aria-describedby={quickCreateError ? 'quick-create-error' : undefined}
                  className="action-primary px-5 py-2 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-semibold shadow-sm"
                >
                  {creatingCustomer ? t("در حال ثبت...") : t("ثبت و انتخاب")}
                </button>
              </div>
            </form>
          </div>
        </dialog>
      )}
    </div>
  );
};
