import streamlit as st
import pandas as pd
import numpy as np
import plotly
import plotly.graph_objects as go
from datetime import datetime, date
import locale

# Set locale to Norwegian
try:
    locale.setlocale(locale.LC_ALL, 'nb_NO.UTF-8')
except:
    try:
        locale.setlocale(locale.LC_ALL, 'nb_NO')
    except:
        locale.setlocale(locale.LC_ALL, '')

def calculate_monthly_payment(principal, annual_rate, years):
    """Calculate the monthly mortgage payment"""
    monthly_rate = annual_rate / 12 / 100
    num_payments = years * 12
    return principal * (monthly_rate * (1 + monthly_rate)**num_payments) / ((1 + monthly_rate)**num_payments - 1)

def process_extra_payments(extra_payments_input):
    """Convert extra payments input to a dictionary"""
    extra_payments = {}
    if extra_payments_input:
        for payment in extra_payments_input.split('\n'):
            if payment.strip():
                date_str, amount = payment.split(',')
                payment_date = datetime.strptime(date_str.strip(), '%Y-%m-%d').date()
                extra_payments[payment_date] = float(amount.strip())
    return extra_payments

def calculate_rental_tax(annual_rental_income, rental_percentage, interest_paid, property_tax, 
                        other_expenses, depreciation, property_value=None):
    """
    Calculate tax on rental income based on Norwegian tax rules
    
    Args:
        annual_rental_income: Total rental income for the year
        rental_percentage: Percentage of the property being rented out (0-100)
        interest_paid: Total interest paid on the mortgage for the year
        property_tax: Annual property tax (eiendomsskatt)
        other_expenses: Other deductible expenses related to rental
        depreciation: Annual depreciation of the property (avskrivning)
        property_value: Value of the property (used for calculating formuesskatt)
        
    Returns:
        Dictionary with tax details
    """
    # If renting out more than 50% of the property
    if rental_percentage > 50:
        # Calculate taxable rental income
        deductible_interest = interest_paid * (rental_percentage / 100)
        deductible_property_tax = property_tax * (rental_percentage / 100)
        total_deductions = deductible_interest + deductible_property_tax + other_expenses + depreciation
        
        taxable_income = max(0, annual_rental_income - total_deductions)
        
        # Calculate tax (22% on net rental income as of 2023)
        income_tax_rate = 0.22
        income_tax = taxable_income * income_tax_rate
        
        return {
            'taxable_income': taxable_income,
            'income_tax': income_tax,
            'effective_tax_rate': (income_tax / annual_rental_income * 100) if annual_rental_income > 0 else 0,
            'deductions': total_deductions
        }
    else:
        # No tax calculation needed if renting out less than 50%
        return {
            'taxable_income': 0,
            'income_tax': 0,
            'effective_tax_rate': 0,
            'deductions': 0
        }

def calculate_amortization_schedule(principal, annual_rate, years, monthly_fee, start_date, rental_income, 
                                   monthly_extra_income, extra_payments, reduce_term=True, reinvest_excess=False,
                                   rental_percentage=0, property_tax=0, other_expenses=0, 
                                   property_value=0, depreciation_percentage=0):
    """Calculate complete amortization schedule with extra payments and tax implications"""
    monthly_rate = annual_rate / 12 / 100
    num_payments = years * 12
    
    # Initial monthly payment calculation
    initial_monthly_payment = calculate_monthly_payment(principal, annual_rate, years)
    
    schedule = []
    remaining_balance = principal
    current_date = start_date
    total_extra_payments = 0
    excess_for_next_month = 0
    reinvested_total = 0
    
    # Calculate annual depreciation if applicable
    annual_depreciation = 0
    if rental_percentage > 50 and property_value > 0 and depreciation_percentage > 0:
        # In Norway, only the building value can be depreciated, not the land value
        # As a rough estimate, we assume building value is 70% of property value
        building_value = property_value * 0.7
        annual_depreciation = building_value * (depreciation_percentage / 100)
    
    # Create a sorted list of extra payment dates for easier lookups
    extra_payment_dates = sorted(extra_payments.keys())
    processed_dates = set()  # To track which dates we've already processed
    
    # Tax tracking variables
    current_year = start_date.year
    yearly_rental_income = 0
    yearly_interest_paid = 0
    yearly_tax_liability = 0
    
    # We'll recalculate for each payment to support reducing monthly payments
    for payment_num in range(1, num_payments + 1):
        if not reduce_term:
            # Recalculate monthly payment based on remaining balance and remaining term
            remaining_months = num_payments - payment_num + 1
            if remaining_months > 0 and remaining_balance > 0:
                monthly_payment = calculate_monthly_payment(remaining_balance, annual_rate, remaining_months/12)
            else:
                monthly_payment = 0
        else:
            # Keep original payment amount
            monthly_payment = initial_monthly_payment
        
        # Calculate interest and principal for this payment
        interest_payment = remaining_balance * monthly_rate
        regular_principal_payment = monthly_payment - interest_payment
        
        # Initialize total principal payment with regular principal
        principal_payment = regular_principal_payment
        
        # Get the next payment date to define our date range
        next_date = date(current_date.year + ((current_date.month) // 12),
                        ((current_date.month) % 12) + 1,
                        min(current_date.day, 28))
        
        # Find any extra payments scheduled on this specific date
        extra_payment = extra_payments.get(current_date, 0)
        
        # Add excess from previous month if reinvest_excess is enabled
        if reinvest_excess and excess_for_next_month > 0:
            reinvested_this_month = excess_for_next_month
            extra_payment += reinvested_this_month
            reinvested_total += reinvested_this_month
            excess_for_next_month = 0
        else:
            reinvested_this_month = 0
        
        # Add extra payment and monthly extra income to principal payment
        principal_payment += extra_payment + monthly_extra_income
        
        # Tax calculations tracking - accumulate yearly values
        yearly_rental_income += rental_income
        yearly_interest_paid += interest_payment
        
        # Calculate effective monthly cost (what the borrower actually pays out of pocket)
        monthly_cost = max(0, monthly_payment + monthly_fee - rental_income - monthly_extra_income)
        
        # Check if we're at the end of a year or the loan has been paid off
        if current_date.month == 12 or remaining_balance - principal_payment <= 0:
            # Calculate tax for the current year
            if rental_percentage > 50:
                monthly_depreciation = annual_depreciation / 12
                months_in_year = current_date.month if current_date.year > start_date.year else (13 - start_date.month)
                
                yearly_depreciation = monthly_depreciation * months_in_year
                yearly_property_tax_portion = property_tax * months_in_year / 12
                yearly_other_expenses_portion = other_expenses * months_in_year / 12
                
                tax_result = calculate_rental_tax(
                    yearly_rental_income, 
                    rental_percentage, 
                    yearly_interest_paid, 
                    yearly_property_tax_portion,
                    yearly_other_expenses_portion, 
                    yearly_depreciation,
                    property_value
                )
                
                yearly_tax_liability = tax_result['income_tax']
                monthly_tax = yearly_tax_liability / months_in_year
            else:
                monthly_tax = 0
                yearly_tax_liability = 0
            
            # Reset yearly tracking variables
            yearly_rental_income = 0
            yearly_interest_paid = 0
            current_year = next_date.year
        else:
            # Estimate monthly tax portion
            if rental_percentage > 50:
                # Estimate monthly tax based on the current month's data
                monthly_rental = rental_income
                monthly_interest = interest_payment
                monthly_depreciation = annual_depreciation / 12
                monthly_property_tax = property_tax / 12
                monthly_other_expenses = other_expenses / 12
                
                monthly_tax_estimate = calculate_rental_tax(
                    monthly_rental * 12,
                    rental_percentage,
                    monthly_interest * 12,
                    monthly_property_tax * 12,
                    monthly_other_expenses * 12,
                    monthly_depreciation * 12
                )['income_tax'] / 12
            else:
                monthly_tax_estimate = 0
            
            monthly_tax = monthly_tax_estimate
        
                        # Adjust monthly cost to include estimated tax
        monthly_cost_after_tax = monthly_cost + monthly_tax
        
        # Calculate after-tax profit from rental income (for reporting purposes)
        after_tax_rental_profit = max(0, rental_income - interest_payment * (rental_percentage / 100)) - monthly_tax
        
        # Calculate excess for reinvestment (only if rental income exceeds interest payment)
        if reinvest_excess and rental_income > interest_payment:
            # For reinvestment, we consider excess as rental income over interest payment
            potential_excess = rental_income - interest_payment
            # But we can only reinvest what's not already being used for principal
            excess_for_next_month = max(0, potential_excess - regular_principal_payment)
            excess_reinvested = excess_for_next_month
        else:
            excess_reinvested = 0
            
        # Update remaining balance - ensure we're reducing by the full principal payment
        remaining_balance = max(0, remaining_balance - principal_payment)
        
        schedule.append({
            'Payment_Date': current_date,
            'Payment_Num': payment_num,
            'Payment': monthly_payment,
            'Principal': principal_payment,
            'Regular_Principal': regular_principal_payment,
            'Interest': interest_payment,
            'Extra_Payment': extra_payment,
            'Monthly_Extra_Income': monthly_extra_income,
            'Excess_Reinvested': excess_reinvested,
            'Remaining_Balance': remaining_balance,
            'Monthly_Fee': monthly_fee,
            'Rental_Income': rental_income,
            'Monthly_Cost': monthly_cost,
            'Monthly_Tax': monthly_tax,
            'Monthly_Cost_After_Tax': monthly_cost_after_tax,
            'After_Tax_Rental_Profit': after_tax_rental_profit,
            'Years': payment_num / 12,
        })
        
        if remaining_balance <= 0:
            break
            
        # Move to next month
        current_date = next_date
    
    return pd.DataFrame(schedule)

def main():
    st.set_page_config(page_title="Boliglånskalkulator", page_icon="🏡", layout="wide")
    
    st.title('Boliglånskalkulator med Utleieinntekter og Skatteberegning 🏡💰📊')
    
    # Tabs for basic, advanced options, and tax calculations
    basic_tab, advanced_tab, tax_tab = st.tabs(["Grunnleggende Oppsett", "Avanserte Alternativer", "Skatteberegning"])
    
    with basic_tab:
        # Input parameters
        col1, col2 = st.columns(2)
        
        with col1:
            principal = st.number_input('Lånebeløp (NOK)', 
                                    min_value=100000, 
                                    value=13000000, 
                                    step=100000,
                                    format='%d')
            
            annual_rate = st.number_input('Årlig nominell rente (%)', 
                                        min_value=0.1, 
                                        max_value=15.0, 
                                        value=5.45, 
                                        step=0.25)
            
            years = st.number_input('Nedbetalingstid (År)', 
                                min_value=1, 
                                max_value=30, 
                                value=30, 
                                step=1)
        
        with col2:
            rental_income = st.number_input('Månedlig utleieinntekt (NOK)', 
                                        min_value=0, 
                                        value=72400, 
                                        step=500,
                                        format='%d')
            
            monthly_extra_income = st.number_input('Fast månedlig ekstra nedbetaling (NOK)',
                                                min_value=0,
                                                value=0,
                                                step=500,
                                                format='%d')
            
            monthly_fee = st.number_input('Månedlig gebyr til banken (NOK)', 
                                        min_value=0, 
                                        value=45, 
                                        step=5,
                                        format='%d')
            
            start_date = st.date_input('Lånets startdato', 
                                    date(2025, 8, 15))
    
    with advanced_tab:
        st.subheader("Ekstra Nedbetalingsalternativer")
        
        # New feature 1: Option to choose between reducing term or monthly payment
        reduce_term = st.radio(
            "Hva skal ekstrainnbetalinger brukes til?",
            ["Redusere nedbetalingstid", "Redusere månedlig betaling"],
            index=0,
            help="Velg om ekstrainnbetalinger skal redusere nedbetalingstiden eller den månedlige innbetalingen"
        ) == "Redusere nedbetalingstid"
        
        # New feature 2: Option to reinvest excess earnings
        reinvest_excess = st.checkbox(
            "Reinvester overskudd fra leieinntekter som ekstra innbetaling neste måned",
            value=False,
            help="Hvis leieinntekter overstiger renter og avdrag, legg til differansen som ekstra innbetaling neste måned"
        )
        
        # Add explanation
        if reinvest_excess:
            st.info("""
            **Hvordan reinvestering fungerer:** Når utleieinntektene er mer enn rentene og avdragene, 
            vil overskuddet automatisk legges til som ekstra innbetaling neste måned. 
            Dette kan betydelig redusere den totale nedbetalingstiden og rentekostnadene.
            """)
        
        if not reduce_term:
            st.info("""
            **Redusert månedlig betaling:** Når du velger dette alternativet, vil 
            ekstrainnbetalinger føre til at den månedlige betalingen blir lavere, 
            men nedbetalingstiden forblir den samme. Dette kan være nyttig hvis 
            du ønsker å redusere dine månedlige utgifter.
            """)
    
    # New Tab for Tax Calculations
    with tax_tab:
        st.subheader("Skatteberegning ved utleie")
        
        st.info("""
        **Skatteberegning ved utleie av bolig:** I Norge gjelder særskilte skatteregler 
        avhengig av hvor stor andel av boligen som leies ut. Hvis du leier ut mer enn 50% av boligen, 
        må du skatte av leieinntektene. Du kan imidlertid også trekke fra en del utgifter.
        """)
        
        rental_percentage = st.slider(
            "Prosent av boligen som leies ut",
            min_value=0,
            max_value=100,
            value=60,
            step=5,
            help="Hvis mer enn 50%, vil skatteberegninger aktiveres"
        )
        
        if rental_percentage > 50:
            st.success("""
            Du leier ut mer enn 50% av boligen. Skattepliktige leieinntekter vil beregnes etter 
            reglene for utleie av fast eiendom. Du kan trekke fra relevante kostnader.
            """)
            
            property_value = st.number_input(
                "Boligens totale verdi (NOK)",
                min_value=0,
                value=16000000,
                step=500000,
                format="%d",
                help="Brukes til å beregne avskrivninger"
            )
            
            property_tax = st.number_input(
                "Årlig eiendomsskatt (NOK)",
                min_value=0,
                value=20000,
                step=1000,
                format="%d"
            )
            
            other_expenses = st.number_input(
                "Andre årlige fradragsberettigede utgifter (NOK)",
                min_value=0,
                value=30000,
                step=5000,
                format="%d",
                help="F.eks. fellesutgifter, vedlikehold, forsikring, etc."
            )
            
            depreciation_percentage = st.number_input(
                "Årlig avskrivningssats (%)",
                min_value=0.0,
                max_value=10.0,
                value=2.0,
                step=0.5,
                help="Typisk 2-4% for boligbygg"
            )
            
            st.info("""
            **Skatteinformasjon:** 
            1. Rentekostnader: Du kan trekke fra den andelen av rentene som tilsvarer utleieprosenten.
            2. Avskrivninger: Du kan avskrive bygningen (ikke tomten) med ca. 2-4% per år.
            3. Vedlikehold og andre kostnader: Du kan trekke fra kostnader knyttet til utleiedelen.
            4. Skattesats: Netto leieinntekt beskattes med 22% (per 2023).
            """)
        else:
            st.success("""
            Du leier ut 50% eller mindre av boligen. I dette tilfellet er leieinntektene 
            skattefrie så lenge du selv bruker minst halvparten av boligen til eget boligformål.
            """)
            
            st.warning("""
            Merk: Selv om leieinntektene er skattefrie, kan det påvirke beregningen av formuesskatt.
            Denne kalkulatoren fokuserer på direkte skatt på leieinntekter og inkluderer ikke
            formuesskatteberegninger. Konsulter en skatterådgiver for fullstendig skatteplanlegging.
            """)
            
            # Set default values for tax calculation parameters when not used
            property_value = 0
            property_tax = 0
            other_expenses = 0
            depreciation_percentage = 0
    
    # Horizontal line for visual separation
    st.markdown("---")
    
    # Extra payments input
    with st.expander("Ekstra Innbetalinger ⬇️", expanded=False):
        st.markdown("Legg til ekstra innbetaling. Velg om du for eksempel skal bruke egenkapital, eller investere bonusen du har fått fra jobb til nedbetaling")
        
        col1, col2, col3 = st.columns([2, 2, 1])
        
        with col1:
            extra_payment_date = st.date_input(
                'Velg dato',
                min_value=start_date,
                value=start_date,
                key='extra_payment_date'
            )
        
        with col2:
            extra_payment_amount = st.number_input(
                'Beløp (NOK)',
                min_value=0,
                value=2000000,
                step=10000,
                format='%d',
                key='extra_payment_amount'
            )
        
        with col3:
            if st.button('Legg til', key='add_payment'):
                current_payments = st.session_state.get('extra_payments', '')
                new_payment = f"{extra_payment_date}, {extra_payment_amount}"
                if current_payments:
                    current_payments = current_payments + '\n' + new_payment
                else:
                    current_payments = new_payment
                st.session_state['extra_payments'] = current_payments
                st.rerun()
        
        # Display and edit current extra payments
        extra_payments_input = st.text_area(
            'Registrerte ekstra innbetalinger',
            value=st.session_state.get('extra_payments', ''),
            height=100,
            key='extra_payments_display',
            help='Du kan redigere eller slette innbetalinger direkte i dette feltet'
        )
        
        if st.button('Nullstill alle ekstra innbetalinger'):
            st.session_state['extra_payments'] = ''
            st.rerun()
    
    # Process the extra payments
    extra_payments = process_extra_payments(extra_payments_input)
    
    # Calculate amortization schedule with tax calculations
    schedule = calculate_amortization_schedule(
        principal, annual_rate, years, monthly_fee,
        start_date, rental_income, monthly_extra_income, extra_payments,
        reduce_term=reduce_term, reinvest_excess=reinvest_excess,
        rental_percentage=rental_percentage, property_tax=property_tax,
        other_expenses=other_expenses, property_value=property_value,
        depreciation_percentage=depreciation_percentage
    )
    
    # Calculate loan term in years
    actual_loan_term_years = len(schedule) / 12
    
    def format_large_number(number):
        # Add thousand separator using Norwegian locale
        formatted_num = f'{abs(number):,.0f}'.replace(',', ' ')  # Replace comma with space for Norwegian style
        if number < 0:
            return f'-{formatted_num} NOK'
        return f'{formatted_num} NOK'

    # Display key metrics in a dashboard-style layout
    st.subheader('Nøkkeltall')
    
    # Calculate key metrics
    monthly_payment = calculate_monthly_payment(principal, annual_rate, years)
    effective_monthly_cost = monthly_payment + monthly_fee - rental_income - monthly_extra_income
    total_interest = schedule['Interest'].sum()
    
    # Calculate total interest we actually pay (after rental income is applied)
    monthly_interest_paid = schedule.apply(lambda row: max(0, row['Interest'] - row['Rental_Income']), axis=1)
    egen_rentekostnad = monthly_interest_paid.sum()
    
    # Calculate average monthly payment (especially important when using reducing payment option)
    average_monthly_payment = schedule['Payment'].mean() if not reduce_term else monthly_payment
    
    # Calculate total savings (if any)
    interest_savings = annual_rate/100 * principal * years - total_interest
    
    # Calculate time savings (if any)
    time_savings = years * 12 - len(schedule)
    time_savings_years = time_savings / 12
    
    # Calculate tax-related metrics
    total_tax = schedule['Monthly_Tax'].sum()
    average_monthly_tax = schedule['Monthly_Tax'].mean()
    effective_monthly_cost_after_tax = schedule['Monthly_Cost_After_Tax'].mean()
    
    # Custom CSS styling with slightly larger font and card-like appearance
    metric_style = """
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px; height: 100%;">
        <p style="margin-bottom: 0px; color: #666;">{label}</p>
        <p style="font-size: 1.4em; font-weight: bold; margin-top: 4px; color: {color};">{value}</p>
        <p style="margin-top: 5px; font-size: 0.8em; color: #666;">{description}</p>
    </div>
    """
    
    # Create a more organized metrics display with tabs and columns
    summary_tab, details_tab, tax_results_tab = st.tabs(["Økonomisk Sammendrag", "Detaljerte Tall", "Skatteresultater"])
    
    with summary_tab:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(metric_style.format(
                label="Månedlig utgift (før skatt)",
                value=format_large_number(effective_monthly_cost),
                description="Din månedlige betaling etter leieinntekter, før skatt",
                color="#1a5276"
            ), unsafe_allow_html=True)
            
            if rental_percentage > 50:
                st.markdown(metric_style.format(
                    label="Månedlig utgift (etter skatt)",
                    value=format_large_number(effective_monthly_cost_after_tax),
                    description="Din månedlige betaling inkludert skatt på leieinntekter",
                    color="#1a5276"
                ), unsafe_allow_html=True)
            
            if not reduce_term:
                st.markdown(metric_style.format(
                    label="Gjennomsnittlig månedlig betaling",
                    value=format_large_number(average_monthly_payment),
                    description="Gjennomsnittlig over lånets levetid",
                    color="#1a5276"
                ), unsafe_allow_html=True)
        
        with col2:
            st.markdown(metric_style.format(
                label="Faktisk nedbetalingstid",
                value=f"{actual_loan_term_years:.2f} år",
                description=f"Opprinnelig nedbetalingstid: {years} år",
                color="#117a65" if actual_loan_term_years < years else "#1a5276"
            ), unsafe_allow_html=True)
            
            if reduce_term and time_savings > 0:
                st.markdown(metric_style.format(
                    label="Tidsbesparelse",
                    value=f"{time_savings_years:.2f} år",
                    description=f"({time_savings} måneder)",
                    color="#117a65"
                ), unsafe_allow_html=True)
        
        with col3:
            st.markdown(metric_style.format(
                label="Sum egen rentekostnad",
                value=format_large_number(egen_rentekostnad),
                description="Rentekostnad etter leieinntekter er fratrukket",
                color="#1a5276"
            ), unsafe_allow_html=True)
            
            if interest_savings > 0:
                st.markdown(metric_style.format(
                    label="Rentebesparelse",
                    value=format_large_number(interest_savings),
                    description="Sammenlignet med opprinnelig låneplan",
                    color="#117a65"
                ), unsafe_allow_html=True)
    
    with details_tab:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(metric_style.format(
                label="Lånets hovedstol",
                value=format_large_number(principal),
                description="Opprinnelig lånebeløp",
                color="#1a5276"
            ), unsafe_allow_html=True)
            
            st.markdown(metric_style.format(
                label="Bankens gebyr (månedlig)",
                value=format_large_number(monthly_fee),
                description="Fast gebyr fra banken hver måned",
                color="#1a5276"
            ), unsafe_allow_html=True)
        
        with col2:
            st.markdown(metric_style.format(
                label="Bankens fortjeneste (total)",
                value=format_large_number(total_interest),
                description="Total rentebeløp over lånets levetid",
                color="#1a5276"
            ), unsafe_allow_html=True)
            
            st.markdown(metric_style.format(
                label="Månedlig rentekostnad (første måned)",
                value=format_large_number(schedule['Interest'].iloc[0]),
                description=f"Basert på årlig rente på {annual_rate}%",
                color="#1a5276"
            ), unsafe_allow_html=True)
        
        with col3:
            st.markdown(metric_style.format(
                label="Månedlig betaling (totalt)",
                value=format_large_number(monthly_payment),
                description="Basisbetaling (før ekstra innbetalinger)",
                color="#1a5276"
            ), unsafe_allow_html=True)
            
            # If we have reinvested excess, show that metric
            total_reinvested = schedule['Excess_Reinvested'].sum() if 'Excess_Reinvested' in schedule.columns else 0
            if reinvest_excess and total_reinvested > 0:
                st.markdown(metric_style.format(
                    label="Totalt reinvestert overskudd",
                    value=format_large_number(total_reinvested),
                    description="Automatisk reinvestert fra overskudd",
                    color="#117a65"
                ), unsafe_allow_html=True)
    
    # New tax results tab
    with tax_results_tab:
        if rental_percentage > 50:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(metric_style.format(
                    label="Total skatt på leieinntekter",
                    value=format_large_number(total_tax),
                    description="Total skatt over lånets levetid",
                    color="#1a5276"
                ), unsafe_allow_html=True)
                
                st.markdown(metric_style.format(
                    label="Gjennomsnittlig månedlig skatt",
                    value=format_large_number(average_monthly_tax),
                    description="Gjennomsnittlig skatt per måned",
                    color="#1a5276"
                ), unsafe_allow_html=True)
            
            with col2:
                # Calculate effective tax rate on rental income
                total_rental_income = schedule['Rental_Income'].sum()
                effective_tax_rate = (total_tax / total_rental_income * 100) if total_rental_income > 0 else 0
                
                st.markdown(metric_style.format(
                    label="Effektiv skattesats på leieinntekter",
                    value=f"{effective_tax_rate:.2f}%",
                    description="Total skatt delt på totale leieinntekter",
                    color="#1a5276"
                ), unsafe_allow_html=True)
                
                # Calculate typical monthly deductions
                annual_depreciation = 0
                if property_value > 0 and depreciation_percentage > 0:
                    building_value = property_value * 0.7  # Estimat: 70% av verdien er bygning, 30% er tomt
                    annual_depreciation = building_value * (depreciation_percentage / 100)
                
                monthly_depreciation = annual_depreciation / 12
                monthly_interest_deduction = schedule['Interest'].iloc[0] * (rental_percentage / 100)
                monthly_expenses_deduction = other_expenses / 12
                monthly_property_tax_deduction = property_tax / 12 * (rental_percentage / 100)
                
                total_monthly_deductions = monthly_depreciation + monthly_interest_deduction + monthly_expenses_deduction + monthly_property_tax_deduction
                
                st.markdown(metric_style.format(
                    label="Typiske månedlige fradrag",
                    value=format_large_number(total_monthly_deductions),
                    description="Summen av fradragsberettigede kostnader per måned",
                    color="#117a65"
                ), unsafe_allow_html=True)


# Visualizations
    st.subheader('Visualiseringer')
    
    # Add tax impact visualization if applicable
    if rental_percentage > 50:
        st.subheader('Skatteeffekt på Månedlig Utgift')
        
        fig_tax = go.Figure()
        
        # Add monthly cost before tax
        fig_tax.add_trace(go.Scatter(
            x=schedule['Payment_Date'],
            y=schedule['Monthly_Cost'],
            name='Månedlig utgift før skatt',
            line=dict(color='green')
        ))
        
        # Add monthly cost after tax
        fig_tax.add_trace(go.Scatter(
            x=schedule['Payment_Date'],
            y=schedule['Monthly_Cost_After_Tax'],
            name='Månedlig utgift etter skatt',
            line=dict(color='red')
        ))
        
        # Add tax amount separately
        fig_tax.add_trace(go.Scatter(
            x=schedule['Payment_Date'],
            y=schedule['Monthly_Tax'],
            name='Månedlig skatt',
            line=dict(color='orange', dash='dot')
        ))
        
        # Add after-tax rental profit
        fig_tax.add_trace(go.Scatter(
            x=schedule['Payment_Date'],
            y=schedule['After_Tax_Rental_Profit'],
            name='Overskudd etter skatt',
            line=dict(color='blue', dash='dot')
        ))
        
        fig_tax.update_layout(
            title='Månedlig utgift med og uten skatt over tid',
            xaxis_title='Dato',
            yaxis_title='Beløp (NOK)',
            hovermode='x unified',
            showlegend=True
        )
        
        st.plotly_chart(fig_tax, use_container_width=True)
    
    # Add new visualization for interest coverage by rental income
    st.subheader('Månedlig Rentedekning fra Utleieinntekter')
        
    # Calculate monthly coverage ratio
    schedule['Interest_Coverage_Ratio'] = schedule['Rental_Income'] / schedule['Interest']
    schedule['Monthly_Interest_Coverage'] = schedule['Rental_Income'] - schedule['Interest']

    # Create visualization for monthly interest coverage
    fig_coverage = go.Figure()

    # Add monthly interest line
    fig_coverage.add_trace(go.Scatter(
        x=schedule['Payment_Date'],
        y=schedule['Interest'],
        name='Månedlig Rentekostnad',
        line=dict(color='red')
    ))

    # Add rental income line
    fig_coverage.add_trace(go.Scatter(
        x=schedule['Payment_Date'],
        y=schedule['Rental_Income'],
        name='Månedlig Leieinntekt',
        line=dict(color='green')
    ))

    # Add coverage ratio as a secondary axis
    fig_coverage.add_trace(go.Scatter(
        x=schedule['Payment_Date'],
        y=schedule['Interest_Coverage_Ratio'],
        name='Dekningsgrad (høyre akse)',
        line=dict(color='blue', dash='dot'),
        yaxis='y2'
    ))

    fig_coverage.update_layout(
        title='Månedlig rentedekning over tid',
        xaxis_title='Dato',
        yaxis_title='Beløp (NOK)',
        yaxis2=dict(
            title='Dekningsgrad',
            overlaying='y',
            side='right'
        ),
        hovermode='x unified',
        showlegend=True
    )

    st.plotly_chart(fig_coverage, use_container_width=True)

    # Add monthly payment visualization
    st.subheader('Månedlig Betaling over Tid')
    
    fig_payment = go.Figure()
    fig_payment.add_trace(go.Scatter(
        x=schedule['Payment_Date'],
        y=schedule['Payment'],
        name='Månedlig Betaling',
        line=dict(color='purple')
    ))
    
    if 'Excess_Reinvested' in schedule.columns and reinvest_excess:
        fig_payment.add_trace(go.Scatter(
            x=schedule['Payment_Date'],
            y=schedule['Excess_Reinvested'],
            name='Reinvestert Overskudd',
            line=dict(color='green', dash='dot')
        ))
    
    fig_payment.update_layout(
        title='Månedlig betaling over tid',
        xaxis_title='Dato',
        yaxis_title='Beløp (NOK)',
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_payment, use_container_width=True)

    # Monthly breakdown
    fig_monthly = go.Figure()
    # Limit to first 360 payments or actual number of payments, whichever is less
    months_to_show = min(360, len(schedule))
    
    fig_monthly.add_trace(go.Bar(
        x=schedule['Payment_Date'][:months_to_show],
        y=schedule['Interest'][:months_to_show],
        name='Renter'
    ))
    fig_monthly.add_trace(go.Bar(
        x=schedule['Payment_Date'][:months_to_show],
        y=schedule['Principal'][:months_to_show],
        name='Avdrag'
    ))
    
    if not reduce_term:
        title = f'Månedlig Fordeling (Redusert månedlig betaling)'
    else:
        title = f'Månedlig Fordeling (Redusert nedbetalingstid)'
    
    fig_monthly.update_layout(
        title=title,
        xaxis_title='Dato',
        yaxis_title='Beløp (NOK)',
        barmode='stack',
        hovermode='x'
    )
    
    st.plotly_chart(fig_monthly, use_container_width=True)
   
    # Balance over time
    fig_balance = go.Figure()
    fig_balance.add_trace(go.Scatter(
        x=schedule['Payment_Date'],
        y=schedule['Remaining_Balance'],
        name='Gjenstående Balanse',
        fill='tozeroy'
    ))
    
    fig_balance.update_layout(
        title='Gjenstående Lånebalanse over Tid',
        xaxis_title='Dato',
        yaxis_title='Balanse (NOK)',
        hovermode='x'
    )
    
    st.plotly_chart(fig_balance, use_container_width=True)
    
    # Detailed table
    st.subheader('Detaljert Nedbetalingsplan')
    
    # Create tabs for different views of the payment plan
    tab1, tab2 = st.tabs(["Fullstendig oversikt", "Forenklet oversikt"])
    
    with tab1:
        # Format numbers in the DataFrame
        display_df = schedule.copy()
        
        # Define columns to show in detailed view
        numeric_columns = ['Payment', 'Principal', 'Regular_Principal', 'Interest', 'Extra_Payment', 
                          'Monthly_Extra_Income', 'Remaining_Balance', 'Monthly_Fee', 
                          'Rental_Income', 'Monthly_Cost']
        
        # Add tax-related columns if applicable
        if rental_percentage > 50:
            numeric_columns.extend(['Monthly_Tax', 'Monthly_Cost_After_Tax', 'After_Tax_Rental_Profit'])
        
        if 'Excess_Reinvested' in display_df.columns:
            numeric_columns.append('Excess_Reinvested')
            
        # Format numeric columns
        for col in numeric_columns:
            display_df[col] = display_df[col].apply(lambda x: f'{x:,.0f} NOK')
        
        display_df['Years'] = display_df['Years'].apply(lambda x: f'{x:.2f}')
        
        # Add percentage paid off column
        display_df['Percent_Paid'] = schedule['Remaining_Balance'].apply(
            lambda x: 100 - (x / principal * 100) if principal > 0 else 100
        ).apply(lambda x: f'{x:.1f}%')
        
        # Rename columns for display
        column_mapping = {
            'Payment_Date': 'Dato',
            'Payment_Num': 'Betaling Nr',
            'Payment': 'Innbetaling',
            'Principal': 'Avdrag',
            'Interest': 'Renter',
            'Extra_Payment': 'Ekstra Innbetaling',
            'Monthly_Extra_Income': 'Fast Månedlig Ekstra',
            'Regular_Principal': 'Standard Avdrag',
            'Remaining_Balance': 'Gjenstående Balanse',
            'Monthly_Fee': 'Månedlig Gebyr',
            'Rental_Income': 'Leieinntekt til banken',
            'Monthly_Cost': 'Egen innbetaling til banken',
            'Years': 'År',
            'Percent_Paid': 'Nedbetalt %',
            'Interest_Coverage_Ratio': 'Dekningsgrad',
            'Monthly_Interest_Coverage': 'Rentedekning',
            'Monthly_Tax': 'Månedlig skatt',
            'Monthly_Cost_After_Tax': 'Månedlig kostnad etter skatt',
            'After_Tax_Rental_Profit': 'Overskudd etter skatt'
        }
        
        if 'Excess_Reinvested' in display_df.columns:
            column_mapping['Excess_Reinvested'] = 'Reinvestert Overskudd'
        
        display_df = display_df.rename(columns=column_mapping)
        
        st.dataframe(
            display_df,
            use_container_width=True,
            height=400
        )
        
    with tab2:
        # Simplified view with fewer columns
        simple_df = schedule.copy()
        
        # Calculate yearly totals and create a yearly summary
        # Get the year from each payment date
        simple_df['Year'] = simple_df['Payment_Date'].apply(lambda x: x.year)
        
        # Group by year and calculate totals
        agg_dict = {
            'Payment': 'sum',
            'Principal': 'sum',
            'Interest': 'sum',
            'Extra_Payment': 'sum',
            'Monthly_Extra_Income': 'sum',
            'Rental_Income': 'sum',
            'Monthly_Cost': 'sum'
        }
        
        # Add tax-related columns to aggregation if applicable
        if rental_percentage > 50 and 'Monthly_Tax' in simple_df.columns:
            agg_dict.update({
                'Monthly_Tax': 'sum',
                'Monthly_Cost_After_Tax': 'sum',
                'After_Tax_Rental_Profit': 'sum'
            })
            
        yearly_summary = simple_df.groupby('Year').agg(agg_dict).reset_index()
        
        # Get remaining balance at end of each year
        year_end_balances = simple_df.groupby('Year').tail(1)[['Year', 'Remaining_Balance']]
        yearly_summary = pd.merge(yearly_summary, year_end_balances, on='Year')
        
        # Add percentage paid off
        yearly_summary['Percent_Paid'] = yearly_summary['Remaining_Balance'].apply(
            lambda x: 100 - (x / principal * 100) if principal > 0 else 100
        )
        
        # Format for display
        display_yearly = yearly_summary.copy()
        yearly_numeric_cols = ['Payment', 'Principal', 'Interest', 'Extra_Payment', 
                              'Monthly_Extra_Income', 'Remaining_Balance', 'Rental_Income', 
                              'Monthly_Cost']
                              
        # Add tax-related columns to formatting if applicable
        if rental_percentage > 50 and 'Monthly_Tax' in display_yearly.columns:
            yearly_numeric_cols.extend(['Monthly_Tax', 'Monthly_Cost_After_Tax', 'After_Tax_Rental_Profit'])
        
        for col in yearly_numeric_cols:
            display_yearly[col] = display_yearly[col].apply(lambda x: f'{x:,.0f} NOK')
        
        display_yearly['Percent_Paid'] = display_yearly['Percent_Paid'].apply(lambda x: f'{x:.1f}%')
        
        # Rename columns
        display_yearly = display_yearly.rename(columns={
            'Year': 'År',
            'Payment': 'Sum innbetaling',
            'Principal': 'Sum avdrag',
            'Interest': 'Sum renter',
            'Extra_Payment': 'Sum ekstra innbetaling',
            'Monthly_Extra_Income': 'Sum fast ekstra',
            'Remaining_Balance': 'Gjenstående balanse',
            'Rental_Income': 'Sum leieinntekt',
            'Monthly_Cost': 'Sum egen innbetaling',
            'Percent_Paid': 'Nedbetalt %',
            'Monthly_Tax': 'Sum skatt',
            'Monthly_Cost_After_Tax': 'Sum kostnader etter skatt',
            'After_Tax_Rental_Profit': 'Sum overskudd etter skatt'
        })
        
        st.dataframe(
            display_yearly,
            use_container_width=True,
            height=400
        )
    
    # Download buttons for different reports
    csv_amortization = schedule.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Last ned komplett nedbetalingsplan",
        data=csv_amortization,
        file_name="nedbetalingsplan.csv",
        mime="text/csv"
    )
    
    # Additional download button for tax report if applicable
    if rental_percentage > 50:
        # Create a tax summary dataframe
        tax_columns = ['Payment_Date', 'Payment_Num', 'Interest', 'Rental_Income', 
                      'Monthly_Tax', 'Monthly_Cost_After_Tax', 'After_Tax_Rental_Profit']
        tax_summary = schedule[tax_columns].copy()
        
        # Add year column for grouping
        tax_summary['Year'] = tax_summary['Payment_Date'].apply(lambda x: x.year)
        
        # Group by year for an annual tax summary
        annual_tax = tax_summary.groupby('Year').agg({
            'Interest': 'sum',
            'Rental_Income': 'sum',
            'Monthly_Tax': 'sum',
            'After_Tax_Rental_Profit': 'sum'
        }).reset_index()
        
        # Add some calculated columns
        annual_tax['Effective_Tax_Rate'] = (annual_tax['Monthly_Tax'] / annual_tax['Rental_Income'] * 100).round(2)
        annual_tax['Deductible_Interest'] = annual_tax['Interest'] * (rental_percentage / 100)
        
        # Format for CSV export
        annual_tax_csv = annual_tax.to_csv(index=False).encode('utf-8')
        
        st.download_button(
            label="Last ned årlig skatterapport",
            data=annual_tax_csv,
            file_name="skatterapport.csv",
            mime="text/csv",
            key="tax_report_download"
        )

if __name__ == "__main__":
    main()
