<template>
  <div class="mw-page">
    <AppHeader scope="materials" />

    <main class="mw-main">
      <header class="mw-hero">
        <h1 class="mw-hero__title">{{ t('wizard.title') }}</h1>
        <p class="mw-hero__privacy">{{ t('wizard.local_storage_hint') }}</p>
        <button type="button" class="mw-hero__clear" data-testid="wizard-clear-local" @click="clearLocalOpen = true">
          {{ t('privacy_local.clear_btn') }}
        </button>
      </header>

      <!-- 整体进度条 -->
      <div class="mw-progress">
        <div class="mw-progress__bar"><div class="mw-progress__fill" :style="{ width: wizard.overallPercent.value + '%' }" /></div>
        <div class="mw-progress__text">{{ wizard.overallPercent.value }}% {{ t('wizard.progress_done') }}</div>
      </div>

      <!-- 分类导航 -->
      <div class="mw-steps">
        <button
          v-for="(cat, i) in wizard.CATEGORIES"
          :key="cat.key"
          type="button"
          class="mw-step"
          :class="{
            'is-active': wizard.state.activeCategory === cat.key,
            'is-done': wizard.categoryDone(cat.key),
          }"
          :data-testid="`mw-step-${cat.key}`"
          @click="wizard.goToCategory(cat.key)"
        >
          <span class="mw-step__icon" :class="`is-${cat.icon}`">
            <CategoryIcon :name="cat.icon" />
          </span>
          <span class="mw-step__label">{{ t(cat.labelKey) }}</span>
          <span v-if="wizard.categoryDone(cat.key)" class="mw-step__check">✓</span>
        </button>
      </div>



      <!-- 当前分类内容 -->
      <section class="mw-panel" :data-testid="`mw-panel-${wizard.activeCategoryDef.value.key}`">
        <h2 class="mw-panel__title">{{ t(wizard.activeCategoryDef.value.labelKey) }}</h2>

        <!-- 签证表格：6 大类收尾 — 在同一页内直接展开 3 个 sub-tab 表单，不再跳转 OrderNew。
             旧版：mw-finish + "开始填写申请表 →" 按钮跳 /orders/new，体验跨度大。
             新版：把 OrderNew.vue 的 3 个表单 section（basic/travel/emergency）原样嵌进来，
             用户填完直接 submit，登录墙在 onSubmit 触发时弹。 -->
         <template v-if="wizard.activeCategoryDef.value.isFormStep">
           <div v-if="formLoading" class="state-block" data-testid="mw-form-loading">
             <span class="spinner" aria-hidden="true"></span> {{ t('common.loading') }}
           </div>
           <div v-else-if="formLoadError" class="state-block state-block--err" data-testid="mw-form-error">
            <p>❌ {{ formLoadError }}</p>
            <button class="form-footer__retry" @click="loadFormData" data-testid="mw-form-retry">{{ t('common.retry') }}</button>
          </div>

          <template v-else>
            <!-- OCR 预填提示 -->
            <div v-if="prefillPercent > 0" class="mw-form-ocr-hint" data-testid="mw-form-ocr-pct">
              <span>{{ t('orders.ocr_prefilled', { percent: prefillPercent }) }}</span>
            </div>

            <!-- Sub-tab 切换 -->
            <nav class="form-tabs" role="tablist" data-testid="mw-form-tabs">
              <button
                v-for="tab in subTabs"
                :key="tab.key"
                class="form-tab"
                :class="{ on: activeTab === tab.key, done: isFormTabDone(tab.key), 'has-missing': formTabMissing[tab.key] > 0 }"
                :data-testid="`mw-form-tab-${tab.key}`"
                role="tab"
                :aria-selected="activeTab === tab.key"
                @click="activeTab = tab.key"
              >
                <span class="form-tab__check" v-if="isFormTabDone(tab.key)">✓</span>
                <span class="form-tab__check form-tab__check--empty" v-else-if="formTabMissing[tab.key] === 0">•</span>
                <span class="form-tab__missing" v-else :data-testid="`mw-form-tab-missing-${tab.key}`" :title="t('orders.sub_tabs_missing_tooltip', { n: formTabMissing[tab.key] })">{{ formTabMissing[tab.key] }}</span>
                <span>{{ t(tab.label) }}</span>
              </button>
              <span class="form-tabs__counter" data-testid="mw-form-sub-counter">
                {{ formSubDoneCount }} / {{ formSubTotal }} {{ t('orders.sub_tabs_done', 'sections completed') }}
              </span>
            </nav>

            <!-- ============== Personal 1 ============== -->
            <section v-show="activeTab === 'personal1'" class="form-card" data-testid="mw-form-section-personal1">
              <h2 class="form-card__title">{{ t('orders.section_personal1') }}</h2>
              <p class="form-card__desc">{{ t('orders.section_personal1_desc') }}</p>
              <div class="form-grid">
                <div class="form-cell">
                  <AppInput v-model="form.surname" :label="t('orders.field_surname')" placeholder="SANTOSO" :error="errors.surname" required maxlength="64" data-testid="mw-form-surname" />
                  <span v-if="ocrMarked.surname" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.given_name" :label="t('orders.field_given_name')" placeholder="BUDI" :error="errors.given_name" required maxlength="64" data-testid="mw-form-given-name" />
                  <span v-if="ocrMarked.given_name" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.native_name" :label="t('orders.field_native_name')" :placeholder="t('orders.placeholder_native_name')" :hint="t('orders.hint_native_name')" :error="errors.native_name" :disabled="dna.native_name" maxlength="64" data-testid="mw-form-native-name" />
                  <DnaCheckbox v-model="dna.native_name" data-testid="mw-form-native-name-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_sex') }}<span class="form-cell__required">*</span></label>
                  <div class="radio-group" data-testid="mw-form-sex">
                    <label class="radio-pill" :class="{ on: form.sex === 'M' }">
                      <input v-model="form.sex" type="radio" value="M" />
                      <span>♂ {{ t('orders.field_sex_male') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.sex === 'F' }">
                      <input v-model="form.sex" type="radio" value="F" />
                      <span>♀ {{ t('orders.field_sex_female') }}</span>
                    </label>
                  </div>
                  <span v-if="errors.sex" class="form-cell__error">{{ errors.sex }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_marital_status') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.marital_status" class="form-cell__select" :class="{ 'is-error': !!errors.marital_status }" data-testid="mw-form-marital">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option value="single">{{ t('orders.marital_single') }}</option>
                    <option value="married">{{ t('orders.marital_married') }}</option>
                    <option value="divorced">{{ t('orders.marital_divorced') }}</option>
                    <option value="widowed">{{ t('orders.marital_widowed') }}</option>
                  </select>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.dob" :label="t('orders.field_dob')" type="date" :error="errors.dob" required :max="todayIso" data-testid="mw-form-dob" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.birth_city" :label="t('orders.field_birth_city')" :error="errors.birth_city" required data-testid="mw-form-birth-city" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_birth_country') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.birth_country" class="form-cell__select" data-testid="mw-form-birth-country">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                </div>
              </div>
            </section>

            <!-- ============== Personal 2 ============== -->
            <section v-show="activeTab === 'personal2'" class="form-card" data-testid="mw-form-section-personal2">
              <h2 class="form-card__title">{{ t('orders.section_personal2') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_nationality') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.nationality" class="form-cell__select" :class="{ 'is-error': !!errors.nationality }" data-testid="mw-form-nationality">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                  <span v-if="errors.nationality" class="form-cell__error">{{ errors.nationality }}</span>
                  <span v-else-if="ocrMarked.nationality" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_has_other_nationality') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-has-other-nationality">
                    <label class="radio-pill" :class="{ on: form.has_other_nationality === 'YES' }">
                      <input v-model="form.has_other_nationality" type="radio" value="YES" />
                      <span>{{ t('common.yes') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.has_other_nationality === 'NO' }">
                      <input v-model="form.has_other_nationality" type="radio" value="NO" />
                      <span>{{ t('common.no') }}</span>
                    </label>
                  </div>
                </div>
                <div class="form-cell" v-if="form.has_other_nationality === 'YES' || dna.other_nationality">
                  <label class="form-cell__label">{{ t('orders.field_other_nationality') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <select v-model="form.other_nationality" :disabled="dna.other_nationality" class="form-cell__select" data-testid="mw-form-other-nationality">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                  <DnaCheckbox v-model="dna.other_nationality" data-testid="mw-form-other-nationality-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.national_id" :label="t('orders.field_national_id')" :placeholder="t('orders.placeholder_national_id')" :hint="t('orders.hint_national_id')" :disabled="dna.national_id" data-testid="mw-form-national-id" />
                  <DnaCheckbox v-model="dna.national_id" data-testid="mw-form-national-id-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_ssn" :label="t('orders.field_us_ssn')" :hint="t('orders.hint_us_ssn')" :disabled="dna.us_ssn" maxlength="11" data-testid="mw-form-us-ssn" />
                  <DnaCheckbox v-model="dna.us_ssn" data-testid="mw-form-us-ssn-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_tax_id" :label="t('orders.field_us_tax_id')" :hint="t('orders.hint_us_tax_id')" :disabled="dna.us_tax_id" maxlength="11" data-testid="mw-form-us-tax-id" />
                  <DnaCheckbox v-model="dna.us_tax_id" data-testid="mw-form-us-tax-id-dna" />
                </div>
              </div>
            </section>

            <!-- ============== Address & Phone ============== -->
            <section v-show="activeTab === 'address'" class="form-card" data-testid="mw-form-section-address">
              <h2 class="form-card__title">{{ t('orders.section_address') }}</h2>
              <div class="form-grid">
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.home_street" :label="t('orders.field_home_street')" :error="errors.home_street" required data-testid="mw-form-home-street" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.home_city" :label="t('orders.field_home_city')" :error="errors.home_city" required data-testid="mw-form-home-city" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.home_state" :label="t('orders.field_home_state')" :hint="t('orders.hint_optional')" :disabled="dna.home_state" data-testid="mw-form-home-state" />
                  <DnaCheckbox v-model="dna.home_state" data-testid="mw-form-home-state-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.home_postal" :label="t('orders.field_home_postal')" :hint="t('orders.hint_optional')" :disabled="dna.home_postal" data-testid="mw-form-home-postal" />
                  <DnaCheckbox v-model="dna.home_postal" data-testid="mw-form-home-postal-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_home_country') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.home_country" class="form-cell__select" :class="{ 'is-error': !!errors.home_country }" data-testid="mw-form-home-country">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.phone" :label="t('orders.field_phone')" :placeholder="t('orders.placeholder_phone')" :error="errors.phone" required inputmode="tel" data-testid="mw-form-phone" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.email" :label="t('orders.field_email')" type="email" :error="errors.email" required data-testid="mw-form-email" />
                </div>
              </div>
            </section>

            <!-- ============== Passport ============== -->
            <section v-show="activeTab === 'passport'" class="form-card" data-testid="mw-form-section-passport">
              <h2 class="form-card__title">{{ t('orders.section_passport') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_passport_type') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.passport_type" class="form-cell__select" data-testid="mw-form-passport-type">
                    <option value="regular">{{ t('orders.passport_type_regular') }}</option>
                    <option value="official">{{ t('orders.passport_type_official') }}</option>
                    <option value="diplomatic">{{ t('orders.passport_type_diplomatic') }}</option>
                  </select>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_no" :label="t('orders.field_passport_no')" placeholder="A12345678" :error="errors.passport_no" required maxlength="12" data-testid="mw-form-passport-no" />
                  <span v-if="ocrMarked.passport_no" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_book_number" :label="t('orders.field_passport_book_number')" :hint="t('orders.hint_passport_book_number')" :disabled="dna.passport_book_number" data-testid="mw-form-passport-book-number" />
                  <DnaCheckbox v-model="dna.passport_book_number" data-testid="mw-form-passport-book-number-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_passport_issue_country') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.passport_issue_country" class="form-cell__select" data-testid="mw-form-passport-issue-country">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                  </select>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_issue_city" :label="t('orders.field_passport_issue_city')" :hint="t('orders.hint_optional_dna')" :disabled="dna.passport_issue_city" data-testid="mw-form-passport-issue-city" />
                  <DnaCheckbox v-model="dna.passport_issue_city" data-testid="mw-form-passport-issue-city-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_issue_date" :label="t('orders.field_passport_issue_date')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.passport_issue_date" data-testid="mw-form-passport-issue-date" />
                  <DnaCheckbox v-model="dna.passport_issue_date" data-testid="mw-form-passport-issue-date-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.passport_expiry" :label="t('orders.field_passport_expiry')" type="date" :error="errors.passport_expiry" :min="minPassportExpiry" data-testid="mw-form-passport-expiry" />
                  <span v-if="ocrMarked.passport_expiry" class="form-cell__ocr">⚡ {{ t('orders.auto_ocr') }}</span>
                </div>
              </div>
            </section>

            <!-- ============== Travel ============== -->
            <section v-show="activeTab === 'travel'" class="form-card" data-testid="mw-form-section-travel">
              <h2 class="form-card__title">{{ t('orders.section_travel') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_destination') }}<span class="form-cell__required">*</span></label>
                  <select v-model="form.destination_id" class="form-cell__select" :class="{ 'is-error': !!errors.destination_id }" data-testid="mw-form-destination">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="d in destinations" :key="d.id" :value="d.id" :disabled="!d.enabled">
                      {{ flagEmoji(d.country_code) }} {{ d.country_name || t(d.country_name_key) }} ({{ d.country_code }}){{ d.enabled ? '' : ' · ' + t('dest.coming_soon') }}
                    </option>
                  </select>
                  <span v-if="errors.destination_id" class="form-cell__error">{{ errors.destination_id }}</span>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_visa_type') }}<span class="form-cell__required">*</span></label>
                  <div class="radio-group" data-testid="mw-form-visa-type">
                    <label class="radio-pill" :class="{ on: form.visa_type === 'tourism' }">
                      <input v-model="form.visa_type" type="radio" value="tourism" />
                      <span>✈ {{ t('orders.visa_tourism') }}</span>
                    </label>
                  </div>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.arrival_date" :label="t('orders.field_arrival_date')" type="date" :error="errors.arrival_date" required :min="todayIso" data-testid="mw-form-arrival" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.departure_date" :label="t('orders.field_departure_date')" type="date" :error="errors.departure_date" required :min="form.arrival_date || todayIso" data-testid="mw-form-departure" />
                </div>
                <div class="form-cell">
                  <AppInput v-model.number="form.stay_days" :label="t('orders.field_stay_days')" type="number" :error="errors.stay_days" min="1" max="365" :hint="stayDaysHint" :disabled="dna.stay_days" data-testid="mw-form-stay-days" />
                  <DnaCheckbox v-model="dna.stay_days" data-testid="mw-form-stay-days-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.flight_no" :label="t('orders.field_flight_no')" :hint="t('orders.hint_optional_dna')" :disabled="dna.flight_no" data-testid="mw-form-flight-no" />
                  <DnaCheckbox v-model="dna.flight_no" data-testid="mw-form-flight-no-dna" />
                </div>
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.hotel_name" :label="t('orders.field_hotel_name')" :hint="t('orders.hint_us_address')" :disabled="dna.hotel_name" data-testid="mw-form-hotel-name" />
                  <DnaCheckbox v-model="dna.hotel_name" data-testid="mw-form-hotel-name-dna" />
                </div>
              </div>
              <div v-if="itineraryText" class="itinerary-preview" data-testid="mw-form-itinerary-preview">
                <div class="itinerary-preview__title">{{ t('orders.itinerary_generated_title') }}</div>
                <ItineraryPreviewTable
                  :days="wizard.state.travelPlan.days"
                  :origin="wizard.state.travelPlan.origin"
                  :destination="wizard.state.travelPlan.destination"
                  :return-origin="wizard.state.travelPlan.returnOrigin"
                  :return-destination="wizard.state.travelPlan.returnDestination"
                />
              </div>
            </section>

            <!-- ============== Companions ============== -->
            <section v-show="activeTab === 'companions'" class="form-card" data-testid="mw-form-section-companions">
              <h2 class="form-card__title">{{ t('orders.section_companions') }}</h2>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_has_companions') }}<span class="form-cell__required">*</span></label>
                  <div class="radio-group" data-testid="mw-form-has-companions">
                    <label class="radio-pill" :class="{ on: form.has_companions === 'YES' }">
                      <input v-model="form.has_companions" type="radio" value="YES" />
                      <span>{{ t('common.yes') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.has_companions === 'NO' }">
                      <input v-model="form.has_companions" type="radio" value="NO" />
                      <span>{{ t('common.no') }}</span>
                    </label>
                  </div>
                </div>
                <template v-if="form.has_companions === 'YES'">
                  <div class="form-cell">
                    <AppInput v-model="form.companion_surname" :label="t('orders.field_companion_surname')" :hint="t('orders.hint_optional')" :disabled="dna.companion_surname" data-testid="mw-form-companion-surname" />
                    <DnaCheckbox v-model="dna.companion_surname" data-testid="mw-form-companion-surname-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.companion_given_name" :label="t('orders.field_companion_given_name')" :hint="t('orders.hint_optional')" :disabled="dna.companion_given_name" data-testid="mw-form-companion-given-name" />
                    <DnaCheckbox v-model="dna.companion_given_name" data-testid="mw-form-companion-given-name-dna" />
                  </div>
                  <div class="form-cell">
                    <label class="form-cell__label">{{ t('orders.field_companion_relation') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                    <select v-model="form.companion_relation" :disabled="dna.companion_relation" class="form-cell__select" data-testid="mw-form-companion-relation">
                      <option value="">— {{ t('orders.placeholder_select') }} —</option>
                      <option v-for="r in relations" :key="r.value" :value="r.value">{{ t(r.label) }}</option>
                    </select>
                    <DnaCheckbox v-model="dna.companion_relation" data-testid="mw-form-companion-relation-dna" />
                  </div>
                </template>
              </div>
            </section>

            <!-- ============== Previous U.S. Travel ============== -->
            <section v-show="activeTab === 'previous_us'" class="form-card" data-testid="mw-form-section-previous-us">
              <h2 class="form-card__title">{{ t('orders.section_previous_us') }}</h2>
              <p class="form-card__desc">{{ t('orders.section_previous_us_desc') }}</p>
              <div class="form-grid">
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_previous_has_visited') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-previous-has-visited">
                    <label class="radio-pill" :class="{ on: form.previous_has_visited === 'YES' }">
                      <input v-model="form.previous_has_visited" type="radio" value="YES" />
                      <span>{{ t('common.yes') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.previous_has_visited === 'NO' }">
                      <input v-model="form.previous_has_visited" type="radio" value="NO" />
                      <span>{{ t('common.no') }}</span>
                    </label>
                  </div>
                </div>
                <template v-if="form.previous_has_visited === 'YES'">
                  <div class="form-cell">
                    <AppInput v-model="form.previous_last_visit_date" :label="t('orders.field_previous_last_visit_date')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.previous_last_visit_date" data-testid="mw-form-previous-last-visit-date" />
                    <DnaCheckbox v-model="dna.previous_last_visit_date" data-testid="mw-form-previous-last-visit-date-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.previous_last_visit_stay_days" :label="t('orders.field_previous_last_visit_stay_days')" :hint="t('orders.hint_stay_days')" :disabled="dna.previous_last_visit_stay_days" data-testid="mw-form-previous-last-visit-stay-days" />
                    <DnaCheckbox v-model="dna.previous_last_visit_stay_days" data-testid="mw-form-previous-last-visit-stay-days-dna" />
                  </div>
                </template>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_previous_has_visa') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-previous-has-visa">
                    <label class="radio-pill" :class="{ on: form.previous_has_visa === 'YES' }">
                      <input v-model="form.previous_has_visa" type="radio" value="YES" />
                      <span>{{ t('common.yes') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.previous_has_visa === 'NO' }">
                      <input v-model="form.previous_has_visa" type="radio" value="NO" />
                      <span>{{ t('common.no') }}</span>
                    </label>
                  </div>
                </div>
                <template v-if="form.previous_has_visa === 'YES'">
                  <div class="form-cell">
                    <AppInput v-model="form.previous_last_visa_date" :label="t('orders.field_previous_last_visa_date')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.previous_last_visa_date" data-testid="mw-form-previous-last-visa-date" />
                    <DnaCheckbox v-model="dna.previous_last_visa_date" data-testid="mw-form-previous-last-visa-date-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.previous_last_visa_number" :label="t('orders.field_previous_last_visa_number')" :hint="t('orders.hint_visa_number')" :disabled="dna.previous_last_visa_number" data-testid="mw-form-previous-last-visa-number" />
                    <DnaCheckbox v-model="dna.previous_last_visa_number" data-testid="mw-form-previous-last-visa-number-dna" />
                  </div>
                </template>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_previous_has_refused') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-previous-has-refused">
                    <label class="radio-pill" :class="{ on: form.previous_has_refused === 'YES' }">
                      <input v-model="form.previous_has_refused" type="radio" value="YES" />
                      <span>{{ t('common.yes') }}</span>
                    </label>
                    <label class="radio-pill" :class="{ on: form.previous_has_refused === 'NO' }">
                      <input v-model="form.previous_has_refused" type="radio" value="NO" />
                      <span>{{ t('common.no') }}</span>
                    </label>
                  </div>
                </div>
              </div>
            </section>

            <!-- ============== U.S. Point of Contact ============== -->
            <section v-show="activeTab === 'us_contact'" class="form-card" data-testid="mw-form-section-us-contact">
              <h2 class="form-card__title">{{ t('orders.section_us_contact') }}</h2>
              <p class="form-card__desc">{{ t('orders.section_us_contact_desc') }}</p>
              <div class="form-grid">
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_surname" :label="t('orders.field_us_contact_surname')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_surname" data-testid="mw-form-us-contact-surname" />
                  <DnaCheckbox v-model="dna.us_contact_surname" data-testid="mw-form-us-contact-surname-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_given_name" :label="t('orders.field_us_contact_given_name')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_given_name" data-testid="mw-form-us-contact-given-name" />
                  <DnaCheckbox v-model="dna.us_contact_given_name" data-testid="mw-form-us-contact-given-name-dna" />
                </div>
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.us_contact_org" :label="t('orders.field_us_contact_org')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_org" data-testid="mw-form-us-contact-org" />
                  <DnaCheckbox v-model="dna.us_contact_org" data-testid="mw-form-us-contact-org-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_us_contact_relation') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <select v-model="form.us_contact_relation" :disabled="dna.us_contact_relation" class="form-cell__select" data-testid="mw-form-us-contact-relation">
                    <option value="">— {{ t('orders.placeholder_select') }} —</option>
                    <option v-for="r in relations" :key="r.value" :value="r.value">{{ t(r.label) }}</option>
                  </select>
                  <DnaCheckbox v-model="dna.us_contact_relation" data-testid="mw-form-us-contact-relation-dna" />
                </div>
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.us_contact_street" :label="t('orders.field_us_contact_street')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_street" data-testid="mw-form-us-contact-street" />
                  <DnaCheckbox v-model="dna.us_contact_street" data-testid="mw-form-us-contact-street-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_city" :label="t('orders.field_us_contact_city')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_city" data-testid="mw-form-us-contact-city" />
                  <DnaCheckbox v-model="dna.us_contact_city" data-testid="mw-form-us-contact-city-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_state" :label="t('orders.field_us_contact_state')" :hint="t('orders.hint_us_state')" :disabled="dna.us_contact_state" data-testid="mw-form-us-contact-state" />
                  <DnaCheckbox v-model="dna.us_contact_state" data-testid="mw-form-us-contact-state-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_zip" :label="t('orders.field_us_contact_zip')" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_zip" data-testid="mw-form-us-contact-zip" />
                  <DnaCheckbox v-model="dna.us_contact_zip" data-testid="mw-form-us-contact-zip-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.us_contact_phone" :label="t('orders.field_us_contact_phone')" :placeholder="'+1 202 555 0100'" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_phone" data-testid="mw-form-us-contact-phone" />
                  <DnaCheckbox v-model="dna.us_contact_phone" data-testid="mw-form-us-contact-phone-dna" />
                </div>
                <div class="form-cell form-cell--full">
                  <AppInput v-model="form.us_contact_email" :label="t('orders.field_us_contact_email')" type="email" :hint="t('orders.hint_optional_dna')" :disabled="dna.us_contact_email" data-testid="mw-form-us-contact-email" />
                  <DnaCheckbox v-model="dna.us_contact_email" data-testid="mw-form-us-contact-email-dna" />
                </div>
              </div>
            </section>

            <!-- ============== Family ============== -->
            <section v-show="activeTab === 'family'" class="form-card" data-testid="mw-form-section-family">
              <h2 class="form-card__title">{{ t('orders.section_family') }}</h2>
              <p class="form-card__desc">{{ t('orders.section_family_desc') }}</p>
              <div class="form-grid">
                <!-- Spouse (only when married) -->
                <template v-if="form.marital_status === 'married'">
                  <div class="form-cell form-cell--full">
                    <h3 class="form-subtitle">{{ t('orders.family_subtitle_spouse') }}</h3>
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.spouse_surname" :label="t('orders.field_spouse_surname')" :hint="t('orders.hint_optional_dna')" :disabled="dna.spouse_surname" data-testid="mw-form-spouse-surname" />
                    <DnaCheckbox v-model="dna.spouse_surname" data-testid="mw-form-spouse-surname-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.spouse_given_name" :label="t('orders.field_spouse_given_name')" :hint="t('orders.hint_optional_dna')" :disabled="dna.spouse_given_name" data-testid="mw-form-spouse-given-name" />
                    <DnaCheckbox v-model="dna.spouse_given_name" data-testid="mw-form-spouse-given-name-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.spouse_dob" :label="t('orders.field_spouse_dob')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.spouse_dob" data-testid="mw-form-spouse-dob" />
                    <DnaCheckbox v-model="dna.spouse_dob" data-testid="mw-form-spouse-dob-dna" />
                  </div>
                  <div class="form-cell">
                    <label class="form-cell__label">{{ t('orders.field_spouse_nationality') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                    <select v-model="form.spouse_nationality" :disabled="dna.spouse_nationality" class="form-cell__select" data-testid="mw-form-spouse-nationality">
                      <option value="">— {{ t('orders.placeholder_select') }} —</option>
                      <option v-for="n in nationalityOptions" :key="n.code" :value="n.code">{{ n.flag }} {{ t(n.nameKey) }}</option>
                    </select>
                    <DnaCheckbox v-model="dna.spouse_nationality" data-testid="mw-form-spouse-nationality-dna" />
                  </div>
                </template>
                <!-- Father -->
                <div class="form-cell form-cell--full">
                  <h3 class="form-subtitle">{{ t('orders.family_subtitle_father') }}</h3>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.father_surname" :label="t('orders.field_father_surname')" :hint="t('orders.hint_optional_dna')" :disabled="dna.father_surname" data-testid="mw-form-father-surname" />
                  <DnaCheckbox v-model="dna.father_surname" data-testid="mw-form-father-surname-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.father_given_name" :label="t('orders.field_father_given_name')" :hint="t('orders.hint_optional_dna')" :disabled="dna.father_given_name" data-testid="mw-form-father-given-name" />
                  <DnaCheckbox v-model="dna.father_given_name" data-testid="mw-form-father-given-name-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.father_dob" :label="t('orders.field_father_dob')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.father_dob" data-testid="mw-form-father-dob" />
                  <DnaCheckbox v-model="dna.father_dob" data-testid="mw-form-father-dob-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_father_in_us') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-father-in-us">
                    <label class="radio-pill" :class="{ on: form.father_in_us === 'YES' }"><input v-model="form.father_in_us" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                    <label class="radio-pill" :class="{ on: form.father_in_us === 'NO' }"><input v-model="form.father_in_us" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                  </div>
                </div>
                <!-- Mother -->
                <div class="form-cell form-cell--full">
                  <h3 class="form-subtitle">{{ t('orders.family_subtitle_mother') }}</h3>
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.mother_surname" :label="t('orders.field_mother_surname')" :hint="t('orders.hint_optional_dna')" :disabled="dna.mother_surname" data-testid="mw-form-mother-surname" />
                  <DnaCheckbox v-model="dna.mother_surname" data-testid="mw-form-mother-surname-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.mother_given_name" :label="t('orders.field_mother_given_name')" :hint="t('orders.hint_optional_dna')" :disabled="dna.mother_given_name" data-testid="mw-form-mother-given-name" />
                  <DnaCheckbox v-model="dna.mother_given_name" data-testid="mw-form-mother-given-name-dna" />
                </div>
                <div class="form-cell">
                  <AppInput v-model="form.mother_dob" :label="t('orders.field_mother_dob')" type="date" :hint="t('orders.hint_optional_dna')" :disabled="dna.mother_dob" data-testid="mw-form-mother-dob" />
                  <DnaCheckbox v-model="dna.mother_dob" data-testid="mw-form-mother-dob-dna" />
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_mother_in_us') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-mother-in-us">
                    <label class="radio-pill" :class="{ on: form.mother_in_us === 'YES' }"><input v-model="form.mother_in_us" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                    <label class="radio-pill" :class="{ on: form.mother_in_us === 'NO' }"><input v-model="form.mother_in_us" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                  </div>
                </div>
                <!-- U.S. Relatives -->
                <div class="form-cell form-cell--full">
                  <h3 class="form-subtitle">{{ t('orders.family_subtitle_us_relatives') }}</h3>
                </div>
                <div class="form-cell">
                  <label class="form-cell__label">{{ t('orders.field_has_us_relatives') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                  <div class="radio-group" data-testid="mw-form-has-us-relatives">
                    <label class="radio-pill" :class="{ on: form.has_us_relatives === 'YES' }"><input v-model="form.has_us_relatives" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                    <label class="radio-pill" :class="{ on: form.has_us_relatives === 'NO' }"><input v-model="form.has_us_relatives" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                  </div>
                </div>
                <template v-if="form.has_us_relatives === 'YES'">
                  <div class="form-cell">
                    <AppInput v-model="form.relative_surname" :label="t('orders.field_relative_surname')" :hint="t('orders.hint_optional_dna')" :disabled="dna.relative_surname" data-testid="mw-form-relative-surname" />
                    <DnaCheckbox v-model="dna.relative_surname" data-testid="mw-form-relative-surname-dna" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="form.relative_given_name" :label="t('orders.field_relative_given_name')" :hint="t('orders.hint_optional_dna')" :disabled="dna.relative_given_name" data-testid="mw-form-relative-given-name" />
                    <DnaCheckbox v-model="dna.relative_given_name" data-testid="mw-form-relative-given-name-dna" />
                  </div>
                  <div class="form-cell">
                    <label class="form-cell__label">{{ t('orders.field_relative_relation') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                    <select v-model="form.relative_relation" :disabled="dna.relative_relation" class="form-cell__select" data-testid="mw-form-relative-relation">
                      <option value="">— {{ t('orders.placeholder_select') }} —</option>
                      <option v-for="r in relations" :key="r.value" :value="r.value">{{ t(r.label) }}</option>
                    </select>
                    <DnaCheckbox v-model="dna.relative_relation" data-testid="mw-form-relative-relation-dna" />
                  </div>
                  <div class="form-cell">
                    <label class="form-cell__label">{{ t('orders.field_relative_status') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                    <select v-model="form.relative_status" :disabled="dna.relative_status" class="form-cell__select" data-testid="mw-form-relative-status">
                      <option value="">— {{ t('orders.placeholder_select') }} —</option>
                      <option value="us_citizen">{{ t('orders.relative_status_us_citizen') }}</option>
                      <option value="lpr">{{ t('orders.relative_status_lpr') }}</option>
                      <option value="other">{{ t('orders.relative_status_other') }}</option>
                    </select>
                    <DnaCheckbox v-model="dna.relative_status" data-testid="mw-form-relative-status-dna" />
                  </div>
                </template>
              </div>
            </section>

            <!-- ============== Work / Education ============== -->
            <section v-show="activeTab === 'work_edu'" class="form-card" data-testid="mw-form-section-work-edu">
              <h2 class="form-card__title">{{ t('orders.section_work_edu') }}</h2>

              <div class="form-grid">
                <div class="form-cell">
                  <AppInput v-model="form.occupation" :label="t('orders.field_occupation')" :hint="t('orders.hint_occupation')" :disabled="dna.occupation" data-testid="mw-form-occupation" />
                  <DnaCheckbox v-model="dna.occupation" data-testid="mw-form-occupation-dna" />
                </div>
              </div>

              <div class="form-subtitle-row">
                <h3 class="form-subtitle">{{ t('orders.add_employment') }}</h3>
                <button type="button" class="form-add-btn" data-testid="mw-form-add-employment" @click="addEmployment">
                  + {{ t('orders.add_employment') }}
                </button>
              </div>
              <div v-if="form.employments.length === 0" class="form-empty-row">
                <span class="form-empty-row__hint">{{ t('orders.hint_optional_dna') }}</span>
              </div>
              <div v-for="(job, idx) in form.employments" :key="'job-' + idx" class="form-repeater-row" :data-testid="`mw-form-employment-${idx}`">
                <div class="form-repeater-row__header">
                  <span class="form-repeater-row__num">#{{ idx + 1 }}</span>
                  <span class="form-repeater-row__hint">{{ t('orders.hint_optional_dna') }}</span>
                  <button type="button" class="form-remove-btn" :data-testid="`mw-form-remove-employment-${idx}`" @click="removeEmployment(idx)">
                    {{ t('orders.remove_row') }}
                  </button>
                </div>
                <div class="form-grid">
                  <div class="form-cell">
                    <AppInput v-model="job.employer_name" :label="t('orders.field_employer_name')" :data-testid="`mw-form-emp-name-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="job.occupation" :label="t('orders.field_occupation')" :data-testid="`mw-form-emp-occ-${idx}`" />
                  </div>
                  <div class="form-cell form-cell--full">
                    <AppInput v-model="job.employer_address" :label="t('orders.work_employer_full')" :data-testid="`mw-form-emp-addr-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="job.from" type="date" :label="t('orders.field_school_from')" :data-testid="`mw-form-emp-from-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="job.to" type="date" :label="t('orders.field_school_to')" :data-testid="`mw-form-emp-to-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="job.monthly_salary" :label="t('orders.field_monthly_salary')" :data-testid="`mw-form-emp-salary-${idx}`" />
                  </div>
                  <div class="form-cell form-cell--full">
                    <AppInput v-model="job.duties" type="textarea" :label="t('orders.field_duties')" :data-testid="`mw-form-emp-duties-${idx}`" />
                  </div>
                </div>
              </div>

              <div class="form-subtitle-row">
                <h3 class="form-subtitle">{{ t('orders.work_subtitle_education') }}</h3>
                <button type="button" class="form-add-btn" data-testid="mw-form-add-education" @click="addEducation">
                  + {{ t('orders.add_education') }}
                </button>
              </div>
              <div v-if="form.educations.length === 0" class="form-empty-row">
                <span class="form-empty-row__hint">{{ t('orders.hint_optional_dna') }}</span>
              </div>
              <div v-for="(edu, idx) in form.educations" :key="'edu-' + idx" class="form-repeater-row" :data-testid="`mw-form-education-${idx}`">
                <div class="form-repeater-row__header">
                  <span class="form-repeater-row__num">#{{ idx + 1 }}</span>
                  <span class="form-repeater-row__hint">{{ t('orders.hint_optional_dna') }}</span>
                  <button type="button" class="form-remove-btn" :data-testid="`mw-form-remove-education-${idx}`" @click="removeEducation(idx)">
                    {{ t('orders.remove_row') }}
                  </button>
                </div>
                <div class="form-grid">
                  <div class="form-cell">
                    <AppInput v-model="edu.school_name" :label="t('orders.edu_school_name')" :data-testid="`mw-form-edu-name-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <label class="form-cell__label">{{ t('orders.edu_qualification') }}<span class="form-cell__hint-dna">{{ t('orders.hint_optional_dna') }}</span></label>
                    <select v-model="edu.qualification" class="form-cell__select" :data-testid="`mw-form-edu-qual-${idx}`">
                      <option value="">— {{ t('orders.placeholder_select') }} —</option>
                      <option value="highschool">{{ t('orders.qualification_highschool') }}</option>
                      <option value="bachelor">{{ t('orders.qualification_bachelor') }}</option>
                      <option value="master">{{ t('orders.qualification_master') }}</option>
                      <option value="phd">{{ t('orders.qualification_phd') }}</option>
                      <option value="other">{{ t('orders.qualification_other') }}</option>
                    </select>
                    <!-- edu 的 qualification 是嵌套在 repeater row 里,每个 row 单独的 dna 标记 — 暂时不上,
                         复杂度收益不匹配。等真用上再加 -->
                  </div>
                  <div class="form-cell form-cell--full">
                    <AppInput v-model="edu.school_address" :label="t('orders.edu_address')" :data-testid="`mw-form-edu-addr-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="edu.course" :label="t('orders.edu_course')" :data-testid="`mw-form-edu-course-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="edu.from" type="date" :label="t('orders.field_school_from')" :data-testid="`mw-form-edu-from-${idx}`" />
                  </div>
                  <div class="form-cell">
                    <AppInput v-model="edu.to" type="date" :label="t('orders.field_school_to')" :data-testid="`mw-form-edu-to-${idx}`" />
                  </div>
                </div>
              </div>
            </section>

            <!-- ============== Security & Background (W50: 5 大类全展开) ============== -->
            <section v-show="activeTab === 'security'" class="form-card" data-testid="mw-form-section-security">
              <h2 class="form-card__title">{{ t('orders.section_security') }}</h2>
              <p class="form-card__desc">{{ t('orders.section_security_desc') }}</p>

              <div class="form-cell">
                <label class="form-cell__label">{{ t('orders.field_security_acknowledged') }}<span class="form-cell__required">*</span></label>
                <div class="radio-group" data-testid="mw-form-security-ack">
                  <label class="radio-pill" :class="{ on: form.security_acknowledged === 'YES' }">
                    <input v-model="form.security_acknowledged" type="radio" value="YES" />
                    <span>{{ t('common.yes') }}</span>
                  </label>
                  <label class="radio-pill" :class="{ on: form.security_acknowledged === 'NO' }">
                    <input v-model="form.security_acknowledged" type="radio" value="NO" />
                    <span>{{ t('common.no') }}</span>
                  </label>
                </div>
              </div>

              <div class="security-part" data-testid="mw-form-sec-p1">
                <h3 class="form-subtitle">{{ t('orders.security_part1_title') }}</h3>
                <p class="form-card__desc">{{ t('orders.security_part1_intro') }}</p>
                <div class="form-grid">
                  <div v-for="q in ['q1','q2','q3','q4']" :key="'p1-'+q" class="form-cell form-cell--full">
                    <p class="security-q">{{ t('orders.security_part1_' + q) }}</p>
                    <div class="radio-group">
                      <label class="radio-pill" :class="{ on: form['sec_p1_' + q] === 'YES' }"><input v-model="form['sec_p1_' + q]" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                      <label class="radio-pill" :class="{ on: form['sec_p1_' + q] === 'NO' }"><input v-model="form['sec_p1_' + q]" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                    </div>
                  </div>
                  <div v-if="secAnyYes(['p1'])" class="form-cell form-cell--full">
                    <AppInput v-model="form.sec_p1_explain" type="textarea" :label="t('orders.security_part1_explain')" data-testid="mw-form-sec-p1-explain" />
                  </div>
                </div>
              </div>

              <div class="security-part" data-testid="mw-form-sec-p2">
                <h3 class="form-subtitle">{{ t('orders.security_part2_title') }}</h3>
                <p class="form-card__desc">{{ t('orders.security_part2_intro') }}</p>
                <div class="form-grid">
                  <div v-for="q in ['q1','q2','q3','q4','q5']" :key="'p2-'+q" class="form-cell form-cell--full">
                    <p class="security-q">{{ t('orders.security_part2_' + q) }}</p>
                    <div class="radio-group">
                      <label class="radio-pill" :class="{ on: form['sec_p2_' + q] === 'YES' }"><input v-model="form['sec_p2_' + q]" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                      <label class="radio-pill" :class="{ on: form['sec_p2_' + q] === 'NO' }"><input v-model="form['sec_p2_' + q]" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                    </div>
                  </div>
                  <div v-if="secAnyYes(['p2'])" class="form-cell form-cell--full">
                    <AppInput v-model="form.sec_p2_explain" type="textarea" :label="t('orders.security_part2_explain')" data-testid="mw-form-sec-p2-explain" />
                  </div>
                </div>
              </div>

              <div class="security-part" data-testid="mw-form-sec-p3">
                <h3 class="form-subtitle">{{ t('orders.security_part3_title') }}</h3>
                <p class="form-card__desc">{{ t('orders.security_part3_intro') }}</p>
                <div class="form-grid">
                  <div v-for="q in ['q1','q2','q3','q4','q5','q6']" :key="'p3-'+q" class="form-cell form-cell--full">
                    <p class="security-q">{{ t('orders.security_part3_' + q) }}</p>
                    <div class="radio-group">
                      <label class="radio-pill" :class="{ on: form['sec_p3_' + q] === 'YES' }"><input v-model="form['sec_p3_' + q]" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                      <label class="radio-pill" :class="{ on: form['sec_p3_' + q] === 'NO' }"><input v-model="form['sec_p3_' + q]" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                    </div>
                  </div>
                  <div v-if="secAnyYes(['p3'])" class="form-cell form-cell--full">
                    <AppInput v-model="form.sec_p3_explain" type="textarea" :label="t('orders.security_part3_explain')" data-testid="mw-form-sec-p3-explain" />
                  </div>
                </div>
              </div>

              <div class="security-part" data-testid="mw-form-sec-p4">
                <h3 class="form-subtitle">{{ t('orders.security_part4_title') }}</h3>
                <p class="form-card__desc">{{ t('orders.security_part4_intro') }}</p>
                <div class="form-grid">
                  <div v-for="q in ['q1','q2','q3']" :key="'p4-'+q" class="form-cell form-cell--full">
                    <p class="security-q">{{ t('orders.security_part4_' + q) }}</p>
                    <div class="radio-group">
                      <label class="radio-pill" :class="{ on: form['sec_p4_' + q] === 'YES' }"><input v-model="form['sec_p4_' + q]" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                      <label class="radio-pill" :class="{ on: form['sec_p4_' + q] === 'NO' }"><input v-model="form['sec_p4_' + q]" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                    </div>
                  </div>
                  <div v-if="secAnyYes(['p4'])" class="form-cell form-cell--full">
                    <AppInput v-model="form.sec_p4_explain" type="textarea" :label="t('orders.security_part4_explain')" data-testid="mw-form-sec-p4-explain" />
                  </div>
                </div>
              </div>

              <div class="security-part" data-testid="mw-form-sec-p5">
                <h3 class="form-subtitle">{{ t('orders.security_part5_title') }}</h3>
                <p class="form-card__desc">{{ t('orders.security_part5_intro') }}</p>
                <div class="form-grid">
                  <div v-for="q in ['q1','q2','q3','q4']" :key="'p5-'+q" class="form-cell form-cell--full">
                    <p class="security-q">{{ t('orders.security_part5_' + q) }}</p>
                    <div class="radio-group">
                      <label class="radio-pill" :class="{ on: form['sec_p5_' + q] === 'YES' }"><input v-model="form['sec_p5_' + q]" type="radio" value="YES" /><span>{{ t('common.yes') }}</span></label>
                      <label class="radio-pill" :class="{ on: form['sec_p5_' + q] === 'NO' }"><input v-model="form['sec_p5_' + q]" type="radio" value="NO" /><span>{{ t('common.no') }}</span></label>
                    </div>
                  </div>
                  <div v-if="secAnyYes(['p5'])" class="form-cell form-cell--full">
                    <AppInput v-model="form.sec_p5_explain" type="textarea" :label="t('orders.security_part5_explain')" data-testid="mw-form-sec-p5-explain" />
                  </div>
                </div>
              </div>
            </section>

            
             <!-- 表单大类底部操作 — 与上传大类不同：prev/submit 而不是 skip/next -->
            <footer class="form-footer" data-testid="mw-form-footer">
              <button class="form-footer__prev" :disabled="!hasPrevFormTab" data-testid="mw-form-prev" @click="goPrevFormTab">← {{ t('orders.btn_prev') }}</button>
              <div class="form-footer__right">
                <button v-if="!isLastFormTab" class="form-footer__next" data-testid="mw-form-next" @click="goNextFormTab">{{ t('orders.btn_next') }} →</button>
                <button v-else class="form-footer__submit" :disabled="submitting" data-testid="mw-form-submit" @click="onSubmitForm">
                  {{ submitting ? t('orders.btn_submitting') : t('orders.btn_submit') }}
                </button>
              </div>
            </footer>
          </template>
        </template>

        <!-- 行程住宿 -->
        <template v-else-if="wizard.activeCategoryDef.value.isTravelPlanner">
          <TravelPlanner
            :plan="wizard.state.travelPlan"
            :destination-name="destinationName"
            :country-code="countryCode"
            :on-generate-itinerary="wizard.generateItinerary"
            :on-compile-itinerary-text="wizard.compileItineraryText"
            :on-rebuild-days="wizard.rebuildTravelDays"
            :on-validate-for-generate="wizard.validateForGenerate"
            :day-city-display-fn="wizard.dayCityDisplay"
            :on-mark-day-field-manual="wizard.markDayFieldManual"
            :on-sync-destination-to-days="wizard.syncDestinationToDays"
          />
        </template>

        <!-- 普通上传大类 -->
        <template v-else>
          <!-- W47c: 当大类下 ≥2 个 items 时切 tab（参考 .form-tab 签证表格样式），
               用户点 tab 切换显示对应上传卡；<2 项保持堆叠原样。
               这样身份证明 (3 项) 用 tab 形式更紧凑，其他 1 项类不动。 -->
          <template v-if="wizard.activeCategoryDef.value.items.length >= 2">
            <nav class="mw-item-tabs" role="tablist" data-testid="mw-item-tabs">
              <button
                v-for="item in wizard.activeCategoryDef.value.items"
                :key="item.key"
                type="button"
                role="tab"
                class="mw-item-tab"
                :class="{ on: activeItemKey === item.key, done: wizard.state.categories[wizard.activeCategoryDef.value.key].items[item.key]?.collected }"
                :aria-selected="activeItemKey === item.key"
                :data-testid="`mw-item-tab-${item.key}`"
                @click="activeItemKey = item.key"
              >
                <span class="mw-item-tab__check" v-if="wizard.state.categories[wizard.activeCategoryDef.value.key].items[item.key]?.collected">✓</span>
                <span>{{ t(item.labelKey) }}</span>
              </button>
            </nav>

            <UploadItemCard
              v-if="activeItem"
              :key="activeItem.key"
              :item-key="activeItem.key"
              :item="activeItem"
              :record="wizard.state.categories[wizard.activeCategoryDef.value.key].items[activeItem.key]"
              :upload-fn="(file, onProgress) => wizard.uploadItem(wizard.activeCategoryDef.value.key, activeItem.key, file, onProgress)"
              :country-code="countryCode"
              :inline-issues="currentItemIssues"
              @remove="wizard.removeItem(wizard.activeCategoryDef.value.key, activeItem.key)"
            />
          </template>
          <template v-else>
            <div class="mw-items">
              <UploadItemCard
                v-for="item in wizard.activeCategoryDef.value.items"
                :key="item.key"
                :item-key="item.key"
                :item="item"
                :record="wizard.state.categories[wizard.activeCategoryDef.value.key].items[item.key]"
                :upload-fn="(file, onProgress) => wizard.uploadItem(wizard.activeCategoryDef.value.key, item.key, file, onProgress)"
                :country-code="countryCode"
                :inline-issues="currentItemIssues"
                @remove="wizard.removeItem(wizard.activeCategoryDef.value.key, item.key)"
              />
            </div>
          </template>

          <!-- 校验问题 — W58: 多 item 时按激活 itemKey 过滤;单 item 大类照旧全显示。
               W62: identity 大类(passport/photo)的 issue 已经在 UploadItemCard 卡内黄框显示,
               这里用 issuesForBottomBlock 过滤掉,只保留 financial/work/travel/form 之类。 -->
          <div v-if="issuesForBottomBlock.length" class="mw-issues" data-testid="mw-issues">
            <div v-for="(iss, i) in issuesForBottomBlock" :key="`${iss.itemKey}-${i}`" class="mw-issue" :class="`is-${iss.severity}`">
              <b>{{ iss.title }}</b>
              <span v-if="iss.detail">{{ iss.detail }}</span>
            </div>
          </div>

          <!-- 参考样本（中英双语）—— 仅 financial / work 显示（身份证明模块不再展示样本，W23） -->
          <MaterialTemplatePreview
            v-if="['financial', 'work'].includes(wizard.activeCategoryDef.value.key)"
            :category-key="wizard.activeCategoryDef.value.key"
            :country-code="countryCode"
          />
        </template>

        <!-- 底部操作 -->
        <div v-if="!wizard.activeCategoryDef.value.isFormStep" class="mw-footer">
          <button
            v-if="wizard.activeCategoryDef.value.skippable && !wizard.categoryDone(wizard.activeCategoryDef.value.key)"
            class="mw-footer__skip"
            data-testid="mw-skip"
            @click="onSkip"
          >
            {{ t('wizard.skip') }}
          </button>
          <button
            class="mw-footer__next"
            :class="{ 'is-disabled': !canAdvance }"
            :disabled="!canAdvance || validating"
            data-testid="mw-next"
            @click="onNext"
          >
            {{ validating ? t('wizard.validating') : t('wizard.next') + ' →' }}
          </button>
        </div>
      </section>
    </main>

    <div v-if="clearLocalOpen" class="mw-clear-modal" role="dialog" aria-modal="true" @click.self="clearLocalOpen = false">
      <div class="mw-clear-modal__box">
        <h3 class="mw-clear-modal__title">{{ t('privacy_local.clear_confirm_title') }}</h3>
        <p class="mw-clear-modal__desc">{{ t('privacy_local.clear_confirm_desc') }}</p>
        <div class="mw-clear-modal__actions">
          <button type="button" class="mw-clear-modal__btn" @click="clearLocalOpen = false">{{ t('common.cancel') }}</button>
          <button type="button" class="mw-clear-modal__btn mw-clear-modal__btn--danger" data-testid="wizard-clear-confirm" @click="onClearLocalData">
            {{ t('privacy_local.clear_confirm_btn') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, h, onMounted, reactive, ref, watch, watchEffect } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import AppHeader from '@/components/AppHeader.vue'
import AppInput from '@/components/AppInput.vue'
import DnaCheckbox from '@/components/DnaCheckbox.vue'
import UploadItemCard from '@/components/UploadItemCard.vue'
import TravelPlanner from '@/components/TravelPlanner.vue'
import MaterialTemplatePreview from '@/components/MaterialTemplatePreview.vue'
import ItineraryPreviewTable from '@/components/ItineraryPreviewTable.vue'
import { useMaterialWizard } from '@/composables/useMaterialWizard'
import { listDestinations } from '@/api/destinations'
import { extractApplicantDraft, createOrder } from '@/api/orders'
import { savePrecheckSnapshot, clearAllLocalVisaData } from '@/utils/localPrivacyStorage'
import { useAuthStore } from '@/stores/auth'
import { useToast } from '@/composables/useToast'
import { FEATURE_RPA } from '@/config/features'
import { buildApplicantDataPayload } from '@/composables/useApplicantProfile'

const route = useRoute()
const router = useRouter()
const { t, locale, te } = useI18n()
const auth = useAuthStore()
const toast = useToast()

const countryCode = (route.query.country || '').toString().toUpperCase()
const visaType = (route.query.visa_type || 'tourism').toString()

const wizard = useMaterialWizard(countryCode, visaType)
const clearLocalOpen = ref(false)

function onClearLocalData() {
  clearAllLocalVisaData()
  clearLocalOpen.value = false
  toast.success(t('privacy_local.clear_success'))
  router.replace({ name: 'MaterialWizard', query: { country: countryCode, visa_type: visaType } })
}
// 组合式函数里的 computed 在 <script setup> 顶层会被自动解包，但这里我们把整个
// wizard 对象透传给 template，所以模板里读取时手动 .value（wizard.overallPercent.value 等）。

// W54 dev/QA 便利: ?step=financial&step=travel 等强制跳到指定 category (跳过 goToCategory 限制)。
// 仅在 query 含 step 时生效；不影响常规用户流程。
onMounted(() => {
  const stepKey = (route.query.step || '').toString()
  if (!stepKey) return
  // 把所有 category 标 validated, 让 goToCategory 不被 "下一未完成" 卡住
  const cats = wizard.state.categories
  for (const k of Object.keys(cats)) {
    cats[k] = cats[k] || {}
    cats[k].validated = true
  }
  wizard.state.activeCategory = stepKey
})

const destinationName = ref('')
listDestinations({ lang: locale.value }).then((list) => {
  const d = (list || []).find((x) => x.country_code === countryCode)
  if (d) destinationName.value = d.country_name
}).catch(() => {})

const FLAG_MAP = {
  US: '🇺🇸', GB: '🇬🇧', AU: '🇦🇺', FR: '🇫🇷', DE: '🇩🇪', IT: '🇮🇹', ES: '🇪🇸',
}
function flagOf(cc) { return FLAG_MAP[cc] || '🌐' }

// 通用 country flag emoji (OrderNew 风格)
function flagEmoji(cc) {
  if (!cc || cc.length !== 2) return '🌐'
  const codePoints = [...cc.toUpperCase()].map((c) => 0x1f1e6 + (c.charCodeAt(0) - 65))
  return String.fromCodePoint(...codePoints)
}

const validating = ref(false)

const currentIssues = computed(() => {
  const cat = wizard.state.categories[wizard.activeCategoryDef.value.key]
  const all = cat?.issues || []
  // W58: 多 item 的大类(≥2 个 items 走 tab)时,按当前激活 itemKey 过滤 issue,
  // 让 passport 提示只出现在 passport tab 下、photo 提示只出现在 photo tab 下。
  // 单 item 的大类(financial/work/travel)没有 tab,沿用旧行为直接全显示。
  const itemCount = wizard.activeCategoryDef.value.items.length
  if (itemCount < 2) return all
  return all.filter((iss) => iss.itemKey === activeItemKey.value)
})

// W62: 给 mw-issues 块用的列表。
// identity 大类(passport/photo)的所有 issue 已经在 UploadItemCard 卡内黄框里显示,
// 这里不再重复堆块,直接返回空数组。
// W68: financial 大类(bank_statement)同样在 UploadItemCard 里通过
// record.bankAnalysis.rules 显示 ⚠️ 行(bank-review box),这里再显示就重复,
// 也直接返回空数组。
const issuesForBottomBlock = computed(() => {
  const catKey = wizard.activeCategoryDef.value?.key
  if (catKey === 'identity' || catKey === 'financial') return []
  return currentIssues.value
})

// W62: 拿到"当前激活 item"的 issue 列表,作为 inlineIssues 传给 UploadItemCard,
// 跟 record.photoWarnings / isBlurry / isComplete 等卡内提示合并到同一个黄框里。
// 这样 passport 卡只显示 1 个黄框(边缘裁切 + 护照号格式异常),photo 卡只显示
// 1 个黄框(未检测到人脸),不再在卡下重复堆出"护照号格式异常"独立红/黄块。
const currentItemIssues = computed(() => {
  const cat = wizard.state.categories[wizard.activeCategoryDef.value.key]
  if (!cat) return []
  const all = cat.issues || []
  const itemCount = wizard.activeCategoryDef.value.items.length
  if (itemCount >= 2) {
    // 多 item 大类:按激活 itemKey 过滤
    return all.filter((iss) => iss.itemKey === activeItemKey.value)
  }
  // 单 item 大类:这个 item 的所有 issue 都给到唯一那张卡
  const onlyKey = wizard.activeCategoryDef.value.items[0]?.key
  if (!onlyKey) return []
  return all.filter((iss) => iss.itemKey === onlyKey || iss.related_material_id === cat.items[onlyKey]?.materialId)
})

const canAdvance = computed(() => wizard.activeCategoryReady.value)

async function onNext() {
  if (!canAdvance.value) {
    // W68: 不要静默 return。把"为啥进不了下一步"明确告诉用户 ——
    // 之前 return 什么都不弹,按钮看着可点但没反应, 用户体感="按钮坏了"。
    // 现在吐一条详细 toast,列出当前分类下到底是哪一个字段缺失/不通过。
    const def = wizard.activeCategoryDef.value
    const blockedReason = describeNextBlockedReason(def)
    toast.error(blockedReason || t('wizard.err_next_blocked'))
    return
  }
  validating.value = true
  try {
    const result = await wizard.validateCategory(wizard.activeCategoryDef.value.key)
    if (result.validated) {
      wizard.goToNextCategory()
    } else {
      // 验证没通过,把 issues 转成 toast 让用户知道错在哪。
      const msgs = (result.issues || []).slice(0, 3).map((i) => {
        const title = typeof i.title === 'string' ? i.title : ''
        const detail = typeof i.detail === 'string' ? i.detail : ''
        return title && detail ? `${title}：${detail}` : (title || detail)
      }).filter(Boolean)
      if (msgs.length) toast.error(msgs.join(' / '))
    }
  } finally {
    validating.value = false
  }
}

// W68: 帮用户诊断"进入下一步点不动"的真因。
// 检查当前激活分类的关键字段,用一个字符串描述哪一项还没填/不满足。
// 仅当 canAdvance 为 false 时被调用。
function describeNextBlockedReason(def) {
  if (def.isFormStep) return null  // form step 不走 canAdvance 控制
  if (def.isTravelPlanner) {
    const p = wizard.state.travelPlan
    const reasons = []
    if (!p.days || p.days.length === 0) reasons.push(t('wizard.err_no_itinerary'))
    if (!p.departDate) reasons.push(t('wizard.err_no_depart_date'))
    if (!p.returnDate) reasons.push(t('wizard.err_no_return_date'))
    const lastIdx = (p.days || []).length - 1
    ;(p.days || []).forEach((d, i) => {
      if (!d.city || !d.city.trim()) reasons.push(t('wizard.err_day_no_city', { n: i + 1 }))
      if (i < lastIdx && (!d.hotel || !d.hotel.trim())) reasons.push(t('wizard.err_day_no_hotel', { n: i + 1 }))
    })
    return reasons.length ? `${t('wizard.err_travel_incomplete')}:${reasons.slice(0, 3).join(t('common.list_sep'))}` : null
  }
  // 通用上传分类:列出哪个 item materialId / error 缺失
  const c = wizard.state.categories[def.key]
  if (!c) return null
  const missing = []
  for (const it of def.items || []) {
    const rec = c.items?.[it.key]
    if (it.optional || it.auto) continue
    if (!rec?.materialId) missing.push(it.labelKey ? t(it.labelKey) : it.key)
    else if (rec.error) missing.push(`${t(it.labelKey)}: ${rec.error}`)
  }
  return missing.length ? `${t('wizard.err_category_incomplete')}:${missing.join(t('common.list_sep'))}` : null
}

function onSkip() {
  wizard.skipCategory(wizard.activeCategoryDef.value.key)
  wizard.goToNextCategory()
}

// ============================================================ //
// 签证表格：6 大类收尾 — 在同一页内直接展开 3 个 sub-tab 表单        //
// 旧版：goToOrderForm() 跳 /orders/new（OrderNew.vue）                  //
// 新版：把 OrderNew.vue 的 3 个 section 嵌到 MaterialWizard 里                //
// ============================================================ //

// ----- 基础数据 -----
const todayIso = new Date().toISOString().slice(0, 10)
const minPassportExpiry = (() => {
  const d = new Date()
  d.setMonth(d.getMonth() + 6)
  return d.toISOString().slice(0, 10)
})()

// fallback destinations (与 OrderNew 同源,防止后端 /v2/destinations 未就绪)
const FALLBACK_DESTINATIONS = [
  { id: 1, country_code: 'US', country_name_key: 'country.us', visa_types: ['tourism'], enabled: true },
  { id: 2, country_code: 'JP', country_name_key: 'country.jp', visa_types: ['tourism'], enabled: false },
  { id: 3, country_code: 'UK', country_name_key: 'country.uk', visa_types: ['tourism'], enabled: false },
  { id: 4, country_code: 'AU', country_name_key: 'country.au', visa_types: ['tourism'], enabled: false },
  { id: 5, country_code: 'CA', country_name_key: 'country.ca', visa_types: ['tourism'], enabled: false },
  { id: 6, country_code: 'DE', country_name_key: 'country.de_schengen', visa_types: ['tourism'], enabled: false },
  { id: 7, country_code: 'FR', country_name_key: 'country.fr_schengen', visa_types: ['tourism'], enabled: false },
  { id: 8, country_code: 'SG', country_name_key: 'country.sg', visa_types: ['tourism'], enabled: false },
  { id: 9, country_code: 'NZ', country_name_key: 'country.nz', visa_types: ['tourism'], enabled: false }
]

const nationalityOptions = [
  { code: 'CN', nameKey: 'country.cn', flag: '🇨🇳' },
  { code: 'ID', nameKey: 'country.id', flag: '🇮🇩' },
  { code: 'VN', nameKey: 'country.vn', flag: '🇻🇳' },
  { code: 'PH', nameKey: 'country.ph', flag: '🇵🇭' },
  { code: 'MY', nameKey: 'country.my', flag: '🇲🇾' },
  { code: 'TH', nameKey: 'country.th', flag: '🇹🇭' },
  { code: 'SG', nameKey: 'country.sg', flag: '🇸🇬' },
  { code: 'US', nameKey: 'country.us', flag: '🇺🇸' },
  { code: 'JP', nameKey: 'country.jp', flag: '🇯🇵' },
  { code: 'GB', nameKey: 'country.gb', flag: '🇬🇧' },
  { code: 'AU', nameKey: 'country.au', flag: '🇦🇺' },
  { code: 'CA', nameKey: 'country.ca', flag: '🇨🇦' },
  { code: 'DE', nameKey: 'country.de', flag: '🇩🇪' },
  { code: 'FR', nameKey: 'country.fr', flag: '🇫🇷' },
  { code: 'KR', nameKey: 'country.kr', flag: '🇰🇷' }
]

const relations = [
  { value: 'spouse', label: 'orders.relation_spouse' },
  { value: 'parent', label: 'orders.relation_parent' },
  { value: 'child', label: 'orders.relation_child' },
  { value: 'sibling', label: 'orders.relation_sibling' },
  { value: 'friend', label: 'orders.relation_friend' },
  { value: 'colleague', label: 'orders.relation_colleague' },
  { value: 'other', label: 'orders.relation_other' }
]

// 表单 sub-tabs — 9 个 section 对应官方 DS-160 一致结构
const subTabs = [
  { key: 'personal1',   label: 'orders.tab_personal1' },
  { key: 'personal2',   label: 'orders.tab_personal2' },
  { key: 'address',     label: 'orders.tab_address' },
  { key: 'passport',    label: 'orders.tab_passport' },
  { key: 'travel',      label: 'orders.tab_travel' },
  { key: 'companions',  label: 'orders.tab_companions' },
  { key: 'previous_us', label: 'orders.tab_previous_us' },
  { key: 'us_contact',  label: 'orders.tab_us_contact' },
  { key: 'family',      label: 'orders.tab_family' },
  { key: 'work_edu',    label: 'orders.tab_work_edu' },
  { key: 'security',    label: 'orders.tab_security' },
]
const activeTab = ref('personal1')

// W47c: 材料大类 item tab 状态（≥2 个 item 时切 tab 用）
const activeItemKey = ref('')
const activeItem = computed(() => {
  const items = wizard.activeCategoryDef.value.items || []
  // 当前激活的 item 不存在时回退到第一项
  return items.find((x) => x.key === activeItemKey.value) || items[0] || null
})
// 切换大类时重置 activeItemKey（默认选中第一项）
watch(() => wizard.activeCategoryDef.value.key, () => {
  const items = wizard.activeCategoryDef.value.items || []
  if (items.length && !items.find((x) => x.key === activeItemKey.value)) {
    activeItemKey.value = items[0].key
  }
}, { immediate: true })

// 表单 state（从 OrderNew.vue 原样搬过来,加自动保存 + 扩 9 个 section 全字段）
const form = reactive({
  // ===== Personal 1 (identity) =====
  surname: '',
  given_name: '',
  native_name: '',
  sex: '',
  marital_status: '',
  dob: '',
  birth_city: '',
  birth_country: '',
  // ===== Personal 2 =====
  nationality: '',
  has_other_nationality: '',
  other_nationality: '',
  national_id: '',
  us_ssn: '',
  us_tax_id: '',
  // ===== Address =====
  home_street: '',
  home_city: '',
  home_state: '',
  home_postal: '',
  home_country: '',
  phone: '',
  email: '',
  // ===== Passport =====
  passport_no: '',
  passport_type: 'regular',
  passport_book_number: '',
  passport_issue_country: '',
  passport_issue_city: '',
  passport_issue_date: '',
  passport_expiry: '',
  // ===== Travel =====
  destination_id: '',
  visa_type: visaType,
  arrival_date: '',
  departure_date: '',
  stay_days: 7,
  flight_no: '',
  hotel_name: '',
  // ===== Companions =====
  has_companions: '',
  companion_surname: '',
  companion_given_name: '',
  companion_relation: '',
  // ===== Previous U.S. =====
  previous_has_visited: '',
  previous_last_visit_date: '',
  previous_last_visit_stay_days: '',
  previous_has_visa: '',
  previous_last_visa_date: '',
  previous_last_visa_number: '',
  previous_has_refused: '',
  // ===== U.S. Contact =====
  us_contact_surname: '',
  us_contact_given_name: '',
  us_contact_org: '',
  us_contact_relation: '',
  us_contact_street: '',
  us_contact_city: '',
  us_contact_state: '',
  us_contact_zip: '',
  us_contact_phone: '',
  us_contact_email: '',
  // ===== Family =====
  spouse_surname: '',
  spouse_given_name: '',
  spouse_dob: '',
  spouse_nationality: '',
  father_surname: '',
  father_given_name: '',
  father_dob: '',
  father_in_us: '',
  mother_surname: '',
  mother_given_name: '',
  mother_dob: '',
  mother_in_us: '',
  has_us_relatives: '',
  relative_surname: '',
  relative_given_name: '',
  relative_relation: '',
  relative_status: '',
  // ===== Work / Education =====
  occupation: '',
  // 动态多段(W50:官方 DS-160 允许多段教育 + 工作经历)
  educations: [],     // [{ school_name, school_address, course, qualification, from, to }]
  employments: [],    // [{ employer_name, employer_address, occupation, monthly_salary, duties, from, to }]
  has_education: '',
  school_name: '',     // 保留:兼容旧 UI 单段(可忽略)
  course_of_study: '',
  school_from: '',
  school_to: '',
  prev_employer: '',
  // ===== Security & Background — 5 大类(每类多题 + 1 个 textarea) =====
  security_acknowledged: '',
  // Part 1 — 健康
  sec_p1_q1: '', sec_p1_q2: '', sec_p1_q3: '', sec_p1_q4: '', sec_p1_explain: '',
  // Part 2 — 犯罪/安全
  sec_p2_q1: '', sec_p2_q2: '', sec_p2_q3: '', sec_p2_q4: '', sec_p2_q5: '', sec_p2_explain: '',
  // Part 3 — 移民/签证
  sec_p3_q1: '', sec_p3_q2: '', sec_p3_q3: '', sec_p3_q4: '', sec_p3_q5: '', sec_p3_q6: '', sec_p3_explain: '',
  // Part 4 — 公共福利
  sec_p4_q1: '', sec_p4_q2: '', sec_p4_q3: '', sec_p4_explain: '',
  // Part 5 — 其他
  sec_p5_q1: '', sec_p5_q2: '', sec_p5_q3: '', sec_p5_q4: '', sec_p5_explain: '',
  // ===== Legacy 紧急联系人(保留兼容) =====
  emergency_name: '',
  emergency_phone: '',
  emergency_relation: '',
})
// DS-160 风格 "Does Not Apply" checkbox — 勾上时该字段视为不适用(后端提交时跳过)
// 命名规则: dna.<field_name>;勾上后字段自动 disabled + 值清空(由 watcher 同步)
const dna = reactive({
  // Personal 1
  native_name: false,
  // Personal 2
  has_other_nationality: false,
  other_nationality: false,
  national_id: false,
  us_ssn: false,
  us_tax_id: false,
  // Address
  home_state: false,
  home_postal: false,
  // Passport
  passport_book_number: false,
  passport_issue_city: false,
  passport_issue_date: false,
  // Travel
  stay_days: false,        // 数字字段,DS-160 上允许勾 Does Not Apply
  flight_no: false,
  hotel_name: false,
  // Companions
  companion_surname: false,
  companion_given_name: false,
  companion_relation: false,
  // Previous US — 3 个 YES/NO radio 不需要 dna(NO 已经表示"否");
  // 2 个日期和 1 个签证号需要
  previous_last_visit_date: false,
  previous_last_visit_stay_days: false,
  previous_last_visa_date: false,
  previous_last_visa_number: false,
  // US Contact
  us_contact_surname: false,
  us_contact_given_name: false,
  us_contact_org: false,
  us_contact_relation: false,
  us_contact_street: false,
  us_contact_city: false,
  us_contact_state: false,
  us_contact_zip: false,
  us_contact_phone: false,
  us_contact_email: false,
  // Family
  spouse_surname: false,
  spouse_given_name: false,
  spouse_dob: false,
  spouse_nationality: false,
  father_surname: false,
  father_given_name: false,
  father_dob: false,
  mother_surname: false,
  mother_given_name: false,
  mother_dob: false,
  relative_surname: false,
  relative_given_name: false,
  relative_relation: false,
  relative_status: false,
  // Work / Education
  occupation: false,
})
const errors = reactive({
  surname: '', given_name: '', sex: '', dob: '', nationality: '',
  passport_no: '', passport_expiry: '', destination_id: '',
  arrival_date: '', departure_date: '', stay_days: '',
  emergency_name: '', emergency_phone: '', emergency_relation: ''
})
const ocrMarked = reactive({
  surname: false, given_name: false, sex: false, dob: false,
  nationality: false, passport_no: false, passport_expiry: false,
  // W50: 护照 MRZ 全字段 OCR 标记
  passport_type: false, passport_issue_country: false,
  passport_issue_city: false, passport_issue_date: false,
  passport_book_number: false, native_name: false,
})
const prefillPercent = ref(0)
const itineraryText = ref('')

const destinations = ref([])
const formLoading = ref(false)
const formLoadError = ref('')
const submitting = ref(false)

// 行程天数提示
const stayDaysHint = computed(() => {
  if (form.arrival_date && form.departure_date) {
    const a = new Date(form.arrival_date)
    const b = new Date(form.departure_date)
    if (b > a) {
      const days = Math.round((b - a) / 86400000) + 1
      return t('orders.stay_days_hint', { next: t('orders.stay_days_auto'), days })
    }
  }
  return ''
})

watch([() => form.arrival_date, () => form.departure_date], () => {
  if (form.arrival_date && form.departure_date) {
    const a = new Date(form.arrival_date)
    const b = new Date(form.departure_date)
    if (b >= a && !dna.stay_days) {
      form.stay_days = Math.round((b - a) / 86400000) + 1
    }
  }
})

// DS-160 风格 Does Not Apply 联动:
// - 勾上 dna[field] = true → 清空 form[field](让 disabled 后值是空的)
// - 取消勾选: 字段保持空值(用户需重新填写,符合 DS-160 真实行为)
watch(() => Object.entries(dna).map(([k, v]) => `${k}:${v}`).join('|'), () => {
  for (const k in dna) {
    if (dna[k]) {
      // 数字字段置 null/0 都行,后端 schema 看怎么接;这里置空字符串最安全
      form[k] = ''
    }
  }
})

// 表单自动保存 — key 包含 countryCode+visaType,避免不同国家/签种串数据
// TTL 7 天(跟 OrderNew 的 ordernew_draft 一致)
const FORM_DRAFT_KEY = 'wizard.orderForm'
const FORM_DRAFT_TTL_MS = 7 * 24 * 3600 * 1000

function draftKey() {
  return `${FORM_DRAFT_KEY}.${countryCode || 'na'}.${visaType || 'na'}`
}

function saveFormDraft() {
  try {
    localStorage.setItem(draftKey(), JSON.stringify({
      form: { ...form },
      errors: { ...errors },
      ocrMarked: { ...ocrMarked },
      activeTab: activeTab.value,
      prefillPercent: prefillPercent.value,
      itineraryText: itineraryText.value,
      savedAt: Date.now()
    }))
  } catch { /* quota / privacy mode, ignore */ }
}

function loadFormDraft() {
  try {
    const raw = localStorage.getItem(draftKey())
    if (!raw) return false
    const draft = JSON.parse(raw)
    if (!draft || !draft.form) return false
    if (Date.now() - (draft.savedAt || 0) > FORM_DRAFT_TTL_MS) {
      localStorage.removeItem(draftKey())
      return false
    }
    Object.assign(form, draft.form)
    Object.assign(errors, draft.errors || {})
    Object.assign(ocrMarked, draft.ocrMarked || {})
    if (draft.activeTab) activeTab.value = draft.activeTab
    if (typeof draft.prefillPercent === 'number') prefillPercent.value = draft.prefillPercent
    if (typeof draft.itineraryText === 'string') itineraryText.value = draft.itineraryText
    return true
  } catch {
    return false
  }
}

// 表单状态变化 → 自动保存(去抖,避免每个键都写 localStorage)
let _saveTimer = null
function scheduleSaveFormDraft() {
  if (_saveTimer) clearTimeout(_saveTimer)
  _saveTimer = setTimeout(saveFormDraft, 300)
}

// 监听 form + activeTab + itineraryText 任一变化都自动保存
// (errors 是 form 的派生,会被 form watch 顺带捕获)
watch(form, scheduleSaveFormDraft, { deep: true })
watch(activeTab, scheduleSaveFormDraft)
watch(itineraryText, scheduleSaveFormDraft)
watch(prefillPercent, scheduleSaveFormDraft)

// ---- 加载数据 (destinations + material OCR prefill) ----
async function loadFormData() {
  formLoading.value = true
  formLoadError.value = ''
  try {
    // 1) destinations — 硬编码兜底 + 真实接口
    destinations.value = FALLBACK_DESTINATIONS
    try {
      const real = await listDestinations({ lang: locale.value || 'zh-CN' })
      if (Array.isArray(real) && real.length > 0) {
        destinations.value = real
      }
    } catch (e) {
      console.warn('[materialwizard] destinations load failed, using fallback:', e?.message)
    }

    // 2) 选 destination_id (与 countryCode 关联)
    if (countryCode) {
      const d = destinations.value.find((x) => x.country_code === countryCode)
      if (d) form.destination_id = d.id
    }
    if (!form.destination_id && destinations.value.length) {
      const us = destinations.value.find((x) => x.country_code === 'US' && x.enabled)
      form.destination_id = (us || destinations.value[0]).id
    }

    // 3) 恢复 draft — 7 天内有效,避免重填
    loadFormDraft()

    // 4) OCR 预填 — 从向导本地 ocrFields 灌进 form（不再拉服务端 material）
    const pseudoMats = []
    for (const cat of Object.values(wizard.state.categories || {})) {
      for (const rec of Object.values(cat.items || {})) {
        if (rec?.ocrFields) {
          pseudoMats.push({ material_type: 'passport', ocr_result: rec.ocrFields })
        }
      }
    }
    if (pseudoMats.length > 0) {
      const { draft, percent } = extractApplicantDraft(pseudoMats)
      prefillPercent.value = percent
      // 已经有用户填的内容（来自 draft 恢复）就保留,否则用 OCR
      for (const k of Object.keys(draft)) {
        if (draft[k] && !form[k]) {
          form[k] = draft[k]
          ocrMarked[k] = true
        }
      }
    }

    // 5) 默认旅行日期 (没有 draft 也没用户输入时给个起点)
    if (!form.arrival_date) {
      const a = new Date(); a.setDate(a.getDate() + 30)
      form.arrival_date = a.toISOString().slice(0, 10)
    }
    if (!form.departure_date) {
      const b = new Date(); b.setDate(b.getDate() + 37)
      form.departure_date = b.toISOString().slice(0, 10)
    }
    form.visa_type = visaType

    // 6) 从 wizard 拉行程单(MaterialWizard 行程住宿步骤生成)
    if (!itineraryText.value) {
      const wp = wizard.state.travelPlan
      if (wp?.itineraryText) itineraryText.value = wp.itineraryText
    }
  } catch (e) {
    formLoadError.value = e?.message || t('orders.load_failed')
  } finally {
    formLoading.value = false
  }
}

// 进入"签证表格"分类时按需加载 (避免一开始就发请求)
watch(
  () => wizard.activeCategoryDef.value.isFormStep,
  (isForm) => {
    if (isForm && destinations.value.length === 0 && !formLoading.value) {
      loadFormData()
    }
  },
  { immediate: true }
)

// ---- sub-tab 切换 ----
const currentFormTabIndex = computed(() => subTabs.findIndex((x) => x.key === activeTab.value))
const isLastFormTab = computed(() => currentFormTabIndex.value === subTabs.length - 1)
const hasPrevFormTab = computed(() => currentFormTabIndex.value > 0)

function goNextFormTab() {
  // W67: 切下一个 tab 之前,先用 formTabStatus(只查本 tab 的必填字段)校验当前 tab。
  // 之前用 validateTab(activeTab.value) 会走 'basic' / 'emergency' 等旧分支,跨 tab
  // 校验 passport_no 等字段,字段没填时 form.passport_no.toUpperCase() throw,
  // goNextFormTab 整个函数被吞掉,activeTab 不切,用户感觉"点了没反应"。
  if (!formTabStatus(activeTab.value).done) {
    // 出错 tab 的 errors 提示:只对有 validateTab 分支的 3 个 tab 触发细校验
    const keyMap = { personal1: 'basic', security: 'emergency' }
    validateTab(keyMap[activeTab.value] || activeTab.value, { silent: false })
    return
  }
  if (!isLastFormTab.value) {
    activeTab.value = subTabs[currentFormTabIndex.value + 1].key
  }
}
function goPrevFormTab() {
  if (hasPrevFormTab.value) {
    activeTab.value = subTabs[currentFormTabIndex.value - 1].key
  }
}

// 每个 sub-tab 的必填字段列表 — 给 tab 上的角标用。
// 不复用 validateTab: validateTab 走 'basic'/'emergency' 旧 key,还会跨 tab 校验
// (比如 'basic' 会查 passport_no, 而 passport_no 实际在 passport tab),导致
// personal1 看起来填完了却报 missing=1。角标只看自己 tab 的字段,简单直接。
const FORM_TAB_REQUIRED_FIELDS = {
  personal1:   ['surname', 'given_name', 'sex', 'marital_status', 'dob', 'birth_city', 'birth_country'],
  personal2:   ['nationality'],
  address:     ['home_street', 'home_city', 'home_country', 'phone', 'email'],
  passport:    ['passport_type', 'passport_no', 'passport_issue_country'],
  travel:      ['destination_id', 'visa_type', 'arrival_date', 'departure_date'],
  companions:  ['has_companions'],
  previous_us: ['previous_has_visited', 'previous_has_visa', 'previous_has_refused'],
  us_contact:  [],
  family:      [],
  work_edu:    [],
  security:    ['security_acknowledged'],
}
function isFieldFilled(field) {
  const v = form[field]
  if (v === null || v === undefined) return false
  if (typeof v === 'string') return v.trim() !== ''
  if (typeof v === 'number') return !Number.isNaN(v)
  if (typeof v === 'boolean') return v === true
  return !!v
}
function formTabStatus(key) {
  const required = FORM_TAB_REQUIRED_FIELDS[key] || []
  let missing = 0
  for (const f of required) if (!isFieldFilled(f)) missing += 1
  // companions 条件必填: YES 时,姓名/关系也要填
  if (key === 'companions' && form.has_companions === 'YES') {
    for (const f of ['companion_surname', 'companion_given_name', 'companion_relation']) {
      if (!isFieldFilled(f)) missing += 1
    }
  }
  return { done: missing === 0, missing }
}
function isFormTabDone(key) {
  return formTabStatus(key).done
}
const formSubDoneCount = computed(() => subTabs.filter((x) => isFormTabDone(x.key)).length)
const formSubTotal = subTabs.length
// 每个 tab 缺几个字段 — 给 tab 上的角标用
const formTabMissing = computed(() => {
  const m = {}
  for (const tab of subTabs) m[tab.key] = formTabStatus(tab.key).missing
  return m
})

// ---- 校验 ----
function clearFormErrors() {
  Object.keys(errors).forEach((k) => { errors[k] = '' })
}

// W50: 教育/工作 动态多段
function emptyEducation() {
  return { school_name: '', school_address: '', course: '', qualification: '', from: '', to: '' }
}
function emptyEmployment() {
  return { employer_name: '', employer_address: '', occupation: '', from: '', to: '', monthly_salary: '', duties: '' }
}
function addEducation() { form.educations.push(emptyEducation()) }
function removeEducation(idx) { form.educations.splice(idx, 1) }
function addEmployment() { form.employments.push(emptyEmployment()) }
function removeEmployment(idx) { form.employments.splice(idx, 1) }

// W50: Security 5 大类 — 任一题选 YES 时显示对应 explain textarea
function secAnyYes(parts) {
  for (const p of parts) {
    for (let i = 1; i <= 6; i++) {
      if (form[`sec_${p}_q${i}`] === 'YES') return true
    }
  }
  return false
}

function validateTab(tabKey, { silent = false } = {}) {
  if (silent) clearFormErrors()
  let ok = true
  if (tabKey === 'basic') {
    if (!form.surname) { ok = false; if (!silent) errors.surname = t('orders.err_surname') }
    if (!form.given_name) { ok = false; if (!silent) errors.given_name = t('orders.err_given_name') }
    if (!form.sex) { ok = false; if (!silent) errors.sex = t('orders.err_sex') }
    if (!form.dob) { ok = false; if (!silent) errors.dob = t('orders.err_dob') }
    else if (form.dob > todayIso) { ok = false; if (!silent) errors.dob = t('orders.err_dob_future') }
    if (!form.nationality) { ok = false; if (!silent) errors.nationality = t('orders.err_nationality') }
    // W67: 之前 form.passport_no.toUpperCase() 在 undefined 时 throw, validateTab 整个
    // 函数被吞, goNextFormTab 死掉,用户感觉"点了下一步没反应"。改成先判空再 .toUpperCase()。
    if (!form.passport_no) { ok = false; if (!silent) errors.passport_no = t('orders.err_passport_format') }
    else if (form.nationality === 'CN' && !/^[A-Z][0-9]{8}$/.test(form.passport_no.toUpperCase())) {
      ok = false
      if (!silent) errors.passport_no = t('orders.err_passport_format')
    }
    if (form.passport_expiry && form.passport_expiry < minPassportExpiry) {
      ok = false
      if (!silent) errors.passport_expiry = t('orders.err_passport_expiry')
    }
  }
  if (tabKey === 'travel') {
    if (!form.destination_id) { ok = false; if (!silent) errors.destination_id = t('orders.err_required') }
    if (!form.arrival_date) { ok = false; if (!silent) errors.arrival_date = t('orders.err_arrival_date') }
    if (!form.departure_date) { ok = false; if (!silent) errors.departure_date = t('orders.err_departure_date') }
    if (form.arrival_date && form.departure_date && form.departure_date < form.arrival_date) {
      ok = false
      if (!silent) errors.departure_date = t('orders.err_date_range')
    }
    const d = Number(form.stay_days)
    if (!d || d < 1 || d > 365) {
      ok = false
      if (!silent) errors.stay_days = t('orders.err_stay_days')
    }
  }
  if (tabKey === 'emergency') {
    if (!form.emergency_name) { ok = false; if (!silent) errors.emergency_name = t('orders.err_emergency_name') }
    if (!form.emergency_phone) { ok = false; if (!silent) errors.emergency_phone = t('orders.err_emergency_phone') }
    else if (!/^\+?\d{6,20}$/.test(form.emergency_phone.replace(/\s/g, ''))) {
      ok = false
      if (!silent) errors.emergency_phone = t('orders.err_emergency_phone')
    }
    if (!form.emergency_relation) { ok = false; if (!silent) errors.emergency_relation = t('orders.err_emergency_relation') }
  }
  return ok
}

// W67: 走全 11 tab 校验(原来只查 basic / travel / emergency 3 个,剩 8 个 tab
// 完全跳过,用户填完其他 tab 也能点 Next → 一直报"请补全必填"找不到原因)。
// 复用 formTabStatus 算 done;格式校验(手机号/护照号/日期范围)留在 validateTab 里,
// 由出问题的 tab 触发一次 silent:false 让 errors 显示出来。
function validateAllFormTabs() {
  clearFormErrors()
  // 1) 先按 11 tab 顺序算 done,挑第一个未完成的
  const firstMissing = subTabs.find((tab) => !formTabStatus(tab.key).done)
  if (!firstMissing) return true
  // 2) 切到那个 tab,并触发对应 validateTab 把 errors 写进表单
  activeTab.value = firstMissing.key
  // tab key → validateTab key 的映射(只对有专门分支的 3 个 tab 走细校验)
  // 其它 tab 没 validateTab 分支 → validateTab 默认返回 ok=true,errors 留空,
  // 角标 missing 数已经够清楚告诉用户缺哪些字段,不需要再弹 errors。
  const keyMap = { personal1: 'basic', security: 'emergency' }
  try {
    validateTab(keyMap[firstMissing.key] || firstMissing.key, { silent: false })
  } catch (e) {
    // 兜底: validateTab 内部如果 throw(比如字段 undefined 调 .toUpperCase),不让 onSubmitForm 死掉
    console.warn('[validateAllFormTabs] validateTab threw:', e?.message)
  }
  return false
}

// ---- 提交 ----
async function onSubmitForm() {
  if (!validateAllFormTabs()) {
    toast.error(t('orders.err_form_incomplete') || '请补全必填字段')
    return
  }
  // 隐私优先流程：材料仅存浏览器，不再做服务端 material_id 审计
  // 登录墙：未登录时先保存 draft,跳 Login,登录后回跳续提
  if (!auth.isLoggedIn) {
    saveFormDraft() // 确保最后一次必填内容存住
    return router.push({
      name: 'Login',
      query: {
        redirect: route.fullPath,
        intent: 'submit_form',
        hint: 'login_needed'
      }
    })
  }
  submitting.value = true
  try {
    const payload = {
      destination_id: Number(form.destination_id),
      visa_type: form.visa_type,
      material_ids: [],
      applicant_data: buildApplicantDataPayload(form, { dna, itineraryText: itineraryText.value }),
    }
    const order = await createOrder(payload)
    if (FEATURE_RPA) {
      const destCountry = countryCode || (destinations.value.find((d) => d.id === Number(form.destination_id))?.country_code) || ''
      if (destCountry === 'US') {
        savePrecheckSnapshot(order.order_no, wizard.buildMaterialsSnapshot())
      }
    }
    // 提交成功 → 清掉 draft,跳 RpaSubmit
    try { localStorage.removeItem(draftKey()) } catch { /* ignore */ }
    toast.success(t('orders.submit_success'))
    setTimeout(() => {
      const destCountry = countryCode || (destinations.value.find((d) => d.id === Number(form.destination_id))?.country_code) || ''
      const visa = form.visa_type || 'tourism'
      router.push({
        name: 'PaymentCheckout',
        params: { orderNo: order.order_no },
        query: {
          next: FEATURE_RPA ? 'rpa' : 'detail',
          countryCode: destCountry,
          visaType: visa,
        },
      }).catch(() => {
        router.push({ name: 'OrderDetail', params: { orderNo: order.order_no } })
      })
    }, 600)
  } catch (e) {
    toast.error(e?.message || t('orders.submit_failed'))
  } finally {
    submitting.value = false
  }
}

// 登录后从 Login 跳回来 (intent=submit_form) → 自动续提
onMounted(() => {
  auth.hydrate()
  if (auth.isLoggedIn && route.query?.intent === 'submit_form') {
    router.replace({ path: route.path, query: {} })
    // 等 form 状态稳定再提交
    setTimeout(() => onSubmitForm(), 200)
  }
})

// ------------------------------------------------------------------ //
// 分类图标 — 与 Apply.vue 材料预览用的同一套线条图标，保持视觉一致           //
// ------------------------------------------------------------------ //
const CategoryIcon = {
  props: { name: String },
  render() {
    const common = { viewBox: '0 0 24 24', width: 16, height: 16, fill: 'none', 'aria-hidden': 'true' }
    const stroke = { stroke: 'currentColor' }
    switch (this.name) {
      case 'identity':
        return h('svg', common, [
          h('rect', { x: 3, y: 5, width: 18, height: 14, rx: 2.5, ...stroke, 'stroke-width': 1.7 }),
          h('circle', { cx: 8.5, cy: 11, r: 1.8, ...stroke, 'stroke-width': 1.5 }),
          h('path', { d: 'M5.5 16c.6-1.7 1.9-2.5 3-2.5s2.4.8 3 2.5', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M14.5 10h4M14.5 13h4', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'financial':
        return h('svg', common, [
          h('circle', { cx: 12, cy: 12, r: 8.5, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M9.3 9.3c0-1.1 1.1-2 2.7-2s2.7.9 2.7 2c0 2.8-5.4 1.4-5.4 4.2 0 1.1 1.2 2 2.7 2s2.7-.9 2.7-2', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
          h('path', { d: 'M12 6v1.3M12 16.7V18', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
      case 'work':
        return h('svg', common, [
          h('rect', { x: 3, y: 8, width: 18, height: 11, rx: 2, ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M8.5 8V6.5a2 2 0 0 1 2-2h3a2 2 0 0 1 2 2V8', ...stroke, 'stroke-width': 1.7 }),
          h('path', { d: 'M3 13h18', ...stroke, 'stroke-width': 1.5 }),
        ])
      case 'travel':
        return h('svg', common, [
          h('path', { d: 'M13 3.5l-2.4 2.4L4 7.3l-.9 1.6 6.6 1.6-.4 4.3-1.9 1.4.2 1.6 2.9-1 1.6 2.6 1.5-.6-.5-3 4-3 1.6-4.3-1.6-1.6-3.3.9-1-2.9z', ...stroke, 'stroke-width': 1.4, 'stroke-linejoin': 'round' }),
        ])
      case 'form':
      default:
        return h('svg', common, [
          h('path', { d: 'M7 3.5h7l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 19V5A1.5 1.5 0 0 1 7 3.5z', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M14 3.5V8h4', ...stroke, 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
          h('path', { d: 'M9 12.5h6M9 15.5h6', ...stroke, 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
        ])
    }
  },
}
</script>

<style scoped lang="scss">
.mw-page { min-height: 100vh; background: #FFFFFF; }
.mw-main { max-width: 1200px; margin: 0 auto; padding: 32px 24px 80px; }

.mw-hero { text-align: center; margin-bottom: 24px; }
.mw-hero__title {
  font-size: 30px; font-weight: 800; margin: 0 0 6px; letter-spacing: -.5px;
  background: linear-gradient(135deg, #0f172a 0%, #3B6EF5 120%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.mw-hero__privacy {
  margin: 0 auto 10px;
  max-width: 520px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.mw-hero__clear {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
}
.mw-clear-modal {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: center; justify-content: center; padding: 20px;
}
.mw-clear-modal__box {
  background: #fff; border-radius: 12px; padding: 20px; max-width: 400px; width: 100%;
}
.mw-clear-modal__title { margin: 0 0 8px; font-size: 16px; font-weight: 600; }
.mw-clear-modal__desc { margin: 0 0 16px; font-size: 14px; color: #64748b; line-height: 1.5; }
.mw-clear-modal__actions { display: flex; justify-content: flex-end; gap: 8px; }
.mw-clear-modal__btn {
  border: 1px solid #e2e8f0; background: #fff; padding: 8px 14px; border-radius: 8px; cursor: pointer; font-size: 13px;
}
.mw-clear-modal__btn--danger { border-color: #fecaca; color: #b91c1c; background: #fef2f2; }
.mw-hero__sub { font-size: 14px; color: #64748b; margin: 0; }

.mw-progress { margin-bottom: 24px; }
.mw-progress__bar { height: 6px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }
.mw-progress__fill { height: 100%; background: linear-gradient(90deg, #3B6EF5, #6E59F0); border-radius: 999px; transition: width .4s ease; }
.mw-progress__text { font-size: 11px; font-weight: 700; letter-spacing: 1px; color: #94a3b8; text-align: center; margin-top: 8px; }

.mw-steps { display: grid; grid-template-columns: repeat(6, 1fr); gap: 8px; margin-bottom: 24px; }
.mw-step {
  display: flex; flex-direction: column; align-items: center; gap: 6px;
  padding: 12px 6px; border-radius: 12px; border: 1.5px solid transparent; background: transparent;
  cursor: pointer; transition: all .15s ease; position: relative;
  &.is-active { background: #eff6ff; border-color: #3b6ef5; }
  &.is-done .mw-step__icon { background: #ecfdf3; color: #16a34a; }
}
.mw-step__icon {
  width: 30px; height: 30px; border-radius: 9px; background: #f1f5f9; color: #64748b;
  display: flex; align-items: center; justify-content: center;
}
.mw-step__label { font-size: 11px; font-weight: 600; color: #475569; text-align: center; }
.mw-step__check {
  position: absolute; top: 4px; right: 4px; width: 14px; height: 14px; border-radius: 50%;
  background: #16a34a; color: #fff; font-size: 9px; display: flex; align-items: center; justify-content: center;
}

.mw-panel {
  background: #fff; border: 1px solid #e9edf5; border-radius: 20px;
  padding: 28px 30px; box-shadow: 0 8px 28px rgba(15,23,42,.06);
}
.mw-panel__title { font-size: 19px; font-weight: 700; color: #0f172a; margin: 0 0 18px; }

.mw-items { display: flex; flex-direction: column; gap: 14px; }

// ============== W47c: 大类 item tab（≥2 个 item 时使用，参考 .form-tab 样式）==============
.mw-item-tabs {
  display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap;
}
.mw-item-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; font-size: 13px; font-weight: 500;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px; color: var(--ink-3, #64748B); cursor: pointer;
  transition: all .15s;
}
.mw-item-tab:hover { border-color: #3B6EF5; color: #2D5BFF; }
.mw-item-tab.on { background: #3B6EF5; color: #fff; border-color: #3B6EF5; font-weight: 600; }
.mw-item-tab.done { background: rgba(59, 110, 245, .08); color: #3B6EF5; border-color: rgba(59, 110, 245, .35); font-weight: 600; }
.mw-item-tab.done .mw-item-tab__check { color: #3B6EF5; }
.mw-item-tab.on.done { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.mw-item-tab.on.done .mw-item-tab__check { color: #fff; }

.mw-finish { text-align: center; padding: 20px 0; }
.mw-finish__text { color: #475569; font-size: 14px; margin: 0 0 20px; line-height: 1.6; }
.mw-finish__cta {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff; border: 0;
  padding: 14px 28px; border-radius: 14px; font-size: 15px; font-weight: 700; cursor: pointer;
  box-shadow: 0 10px 24px rgba(15,23,42,.18);
}

.mw-issues { margin-top: 18px; display: flex; flex-direction: column; gap: 8px; }
.mw-issues__others { margin-top: 6px; font-size: 12px; color: #64748b; padding: 6px 10px; border-radius: 8px; background: #f8fafc; border: 1px dashed #e2e8f0; }
.mw-issue {
  font-size: 12.5px; padding: 10px 14px; border-radius: 10px; display: flex; flex-direction: column; gap: 2px;
  &.is-error, &.is-critical { background: #fef2f2; color: #b91c1c; }
  &.is-warning { background: #fffbeb; color: #b45309; }
  &.is-info { background: #eff6ff; color: #1e40af; }
}

.mw-footer { display: flex; gap: 12px; justify-content: flex-end; margin-top: 24px; }
.mw-footer__skip {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
  padding: 12px 20px; border-radius: 12px; font-size: 13.5px; font-weight: 600; cursor: pointer;
}
.mw-footer__next {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff; border: 0;
  padding: 12px 26px; border-radius: 12px; font-size: 14px; font-weight: 700; cursor: pointer;
  box-shadow: 0 8px 20px rgba(59,110,245,.25);
  &.is-disabled { background: #e2e8f0; color: #94a3b8; box-shadow: none; cursor: not-allowed; }
}

@media (max-width: 640px) {
  .mw-steps { grid-template-columns: repeat(3, 1fr); }
}

// ============================================================ //
// 签证表格：6 大类收尾 — 嵌在面板里的 OrderNew 风格表单样式            //
// ============================================================ //
.mw-form-ocr-hint {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: #F0FDF4; border: 1px solid #86EFAC;
  border-radius: 999px; font-size: 12px; color: #166534;
  margin-bottom: 16px;
}
.mw-form-ocr-icon { color: #16A34A; }

// ---- Tabs (与 OrderNew 同款) ----
.form-tabs { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; align-items: center; }
.form-tab {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 7px 14px; font-size: 13px; font-weight: 500;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 999px; color: var(--ink-3, #64748B); cursor: pointer;
  transition: all .15s;
}
.form-tab:hover { border-color: #3B6EF5; color: #2D5BFF; }
/* W47c: 统一品牌主色蓝 (跟步骤条 .mw-step.is-active 同源 #3B6EF5)。
   之前 done 用绿 (#16A34A) + active 用蓝 (#3B6EF5), 两种语义两种色 → 割裂。
   现在:
   - active: 蓝填充 + 白字
   - done:   蓝填充(浅) + 蓝字 + 蓝勾 (浅一档, 跟 active 形成层级差但不抢色)
   - todo:   白底灰字
*/
.form-tab.on { background: #3B6EF5; color: #fff; border-color: #3B6EF5; font-weight: 600; }
.form-tab.done { background: rgba(59, 110, 245, .08); color: #3B6EF5; border-color: rgba(59, 110, 245, .35); font-weight: 600; }
.form-tab.done .form-tab__check { color: #3B6EF5; }
.form-tab.on.done { background: #3B6EF5; color: #fff; border-color: #3B6EF5; }
.form-tabs__counter { margin-left: auto; font-size: 12px; font-weight: 600; color: #3B6EF5; background: rgba(59, 110, 245, .08); padding: 6px 12px; border-radius: 999px; letter-spacing: 0.2px; }
.form-tab.on.done .form-tab__check { color: #fff; }
.form-tab__check--empty { color: #94A3B8; }

/* W67: 没填完整的 tab 左边显示一个红色数字角标 (缺几个字段)。
   用户不用点 Next 才知道哪几个 tab 没填完,一眼能看见。
   角标只在 done=false 且 missing>0 时显示; done=true 显示 ✓; 全空显示 •。 */
.form-tab__missing {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 18px; height: 18px; padding: 0 5px;
  border-radius: 999px;
  background: #DC2626; color: #fff;
  font-size: 11px; font-weight: 700; line-height: 1;
  letter-spacing: -0.2px;
  margin-right: 2px;
}
.form-tab.on .form-tab__missing { background: #fff; color: #DC2626; }
.form-tab.has-missing:not(.on) { border-color: rgba(220, 38, 38, .35); }
.form-tab.on .form-tab__check--empty { color: rgba(255,255,255,.7); }

// ---- Form Card ----
.form-card {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 14px; padding: 24px 26px;
  box-shadow: 0 1px 3px rgba(15,23,42,.04);
  margin-bottom: 20px;
  @media (max-width: 480px) { padding: 18px 16px; }
}
.form-card__desc {
  font-size: 13px;
  color: var(--ink-3, #64748B);
  margin: -10px 0 18px;
  line-height: 1.55;
}
.form-subtitle {
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2, #1E293B);
  margin: 12px 0 4px;
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--border, #E2E8F0);
}
.form-subtitle-row {
  display: flex; justify-content: space-between; align-items: center;
  margin: 24px 0 10px;
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--border, #E2E8F0);
  & .form-subtitle { border: 0; margin: 0; padding: 0; }
}
.form-add-btn {
  background: #3b6ef5; color: #fff; border: 0; border-radius: 8px;
  padding: 6px 14px; font-size: 13px; font-weight: 500; cursor: pointer;
  transition: background .15s;
  &:hover { background: #2553d6; }
}
.form-repeater-row {
  background: #f8fafc;
  border: 1px solid var(--border, #e2e8f0);
  border-radius: 10px;
  padding: 14px 16px 4px;
  margin-bottom: 12px;
  &__header {
    display: flex; justify-content: space-between; align-items: center; gap: 12px;
    margin-bottom: 8px;
  }
  &__num {
    font-size: 12px; font-weight: 600; color: #3b6ef5;
    background: #dbeafe; padding: 2px 8px; border-radius: 999px;
    flex: 0 0 auto;
  }
  &__hint {
    flex: 1 1 auto;
    font-size: 11.5px; color: var(--ink-3, #64748B);
    line-height: 1.4;
  }
}
.form-remove-btn {
  background: #fff; color: #b91c1c;
  border: 1px solid #fecaca; border-radius: 6px;
  padding: 4px 10px; font-size: 12px; font-weight: 500;
  cursor: pointer; transition: all .15s;
  &:hover { background: #fef2f2; border-color: #fca5a5; }
}
.form-empty-row {
  border: 1px dashed #e2e8f0; border-radius: 8px;
  padding: 12px 16px; margin-bottom: 12px;
  background: #fafbfc;
  &__hint { font-size: 12.5px; color: #94a3b8; font-style: italic; }
}
.security-part {
  margin-top: 24px;
  padding: 16px 18px 4px;
  background: #f9fafb;
  border-left: 3px solid #3b6ef5;
  border-radius: 6px;
}
.security-q {
  font-size: 13.5px; font-weight: 500; color: #1e293b;
  margin: 4px 0 6px; line-height: 1.5;
}
.form-cell__hint {
  font-size: 12px;
  color: var(--ink-3, #64748B);
  margin-top: 4px;
  line-height: 1.5;
}
.form-cell__hint-dna {
  display: inline-block;
  margin-left: 8px;
  font-size: 11px;
  font-weight: 400;
  color: var(--ink-3, #64748B);
  line-height: 1.4;
}
.form-card__title {
  margin: 0 0 18px; font-size: 17px; font-weight: 600;
  color: var(--ink-1, #0F172A);
  display: flex; align-items: center; gap: 8px;
  &::before {
    content: ''; width: 3px; height: 16px; background: #3B6EF5; border-radius: 2px;
  }
}

.itinerary-preview {
  margin-top: 18px; border: 1px dashed #cbd5e1; border-radius: 12px;
  padding: 14px 16px; background: #f8fafc;
}
.itinerary-preview__title { font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 8px; }
.itinerary-preview__text {
  font-family: 'SF Mono', Menlo, monospace; font-size: 12.5px; color: #0f172a;
  white-space: pre-wrap; margin: 0; line-height: 1.6;
}

.form-grid {
  display: grid; gap: 16px 20px;
  grid-template-columns: 1fr 1fr;
  @media (max-width: 640px) { grid-template-columns: 1fr; }
}
.form-cell { position: relative; display: flex; flex-direction: column; }
.form-cell--full { grid-column: 1 / -1; }
.form-cell__label {
  display: block; font-size: 13px; font-weight: 500;
  color: var(--ink-2, #334155); margin-bottom: 6px;
}
.form-cell__required { color: var(--el-color-danger, #DC2626); margin-left: 2px; }
.form-cell__error { margin-top: 4px; font-size: 12px; color: var(--el-color-danger, #DC2626); }
.form-cell__ocr {
  position: absolute; right: 0; top: 0;
  display: inline-flex; align-items: center; gap: 4px;
  padding: 1px 8px; background: #EAF0FE; color: #2D5BFF;
  border-radius: 999px; font-size: 10px; font-weight: 600;
  letter-spacing: 0.04em;
  margin-top: 0;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.form-cell__select {
  width: 100%; height: 40px;
  border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; padding: 0 12px;
  background: #fff; font-size: 14px; color: var(--ink-1, #0F172A);
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'><path d='M1 1l5 5 5-5' stroke='%2394A3B8' stroke-width='2' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>");
  background-repeat: no-repeat;
  background-position: right 12px center;
  padding-right: 32px;
  transition: border-color .15s, box-shadow .15s;
}
.form-cell__select:focus { outline: none; border-color: #3B6EF5; box-shadow: 0 0 0 3px rgba(59,110,245,.15); }
.form-cell__select.is-error { border-color: #DC2626; }
.radio-group { display: flex; gap: 8px; }
.radio-pill {
  flex: 1; display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 10px 14px;
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 8px; cursor: pointer;
  font-size: 14px; color: var(--ink-2, #334155);
  transition: all .15s;
  input { position: absolute; opacity: 0; pointer-events: none; }
}
.radio-pill:hover { border-color: #3B6EF5; }
.radio-pill.on { background: #EAF0FE; border-color: #3B6EF5; color: #2D5BFF; font-weight: 600; }

// ---- Form Footer ----
.form-footer {
  display: flex; align-items: center; justify-content: space-between;
  gap: 12px; margin-top: 4px;
  @media (max-width: 480px) { flex-direction: column-reverse; align-items: stretch; }
}
.form-footer__right { display: flex; gap: 8px; }
.form-footer__prev,
.form-footer__next,
.form-footer__submit {
  border: 0; cursor: pointer;
  padding: 12px 20px; border-radius: 12px; font-size: 14px; font-weight: 700;
  transition: all .15s;
}
.form-footer__prev {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
}
.form-footer__prev:disabled { opacity: .4; cursor: not-allowed; }
.form-footer__next {
  background: linear-gradient(135deg, #3B6EF5 0%, #6E59F0 100%); color: #fff;
  box-shadow: 0 8px 20px rgba(59,110,245,.25);
}
.form-footer__submit {
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); color: #fff;
  padding: 12px 26px; box-shadow: 0 10px 24px rgba(15,23,42,.18);
}
.form-footer__submit:disabled { opacity: .6; cursor: not-allowed; }
.form-footer__retry {
  background: transparent; border: 1px solid #cbd5e1; color: #64748b;
  padding: 8px 14px; border-radius: 8px; font-size: 13px; cursor: pointer;
  margin-left: 12px;
}

// ---- State Block ----
.state-block {
  background: #fff; border: 1px solid var(--border, #E2E8F0);
  border-radius: 12px; padding: 40px; text-align: center;
  color: var(--ink-3, #64748B); font-size: 14px;
  display: flex; align-items: center; justify-content: center; gap: 10px;
}
.state-block--err { color: #DC2626; }
.state-block--err p { margin: 0; }
.spinner {
  width: 16px; height: 16px; border-radius: 50%;
  border: 2px solid #3B6EF5; border-top-color: transparent;
  animation: spin .7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
