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

def calculate_amortization_schedule(principal, annual_rate, years, monthly_fee, start_date, rental_income, 
                                   monthly_extra_income, extra_payments, reduce_term=True, reinvest_excess=False):
    """Calculate complete amortization schedule with extra payments"""
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
    
    # Create a sorted list of extra payment dates for easier lookups
    extra_payment_dates = sorted(extra_payments.keys())
    processed_dates = set()  # To track which dates we've already processed
    
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
        
        # Calculate effective monthly cost (what the borrower actually pays out of pocket)
        monthly_cost = max(0, monthly_payment + monthly_fee - rental_income - monthly_extra_income)
        
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
            'Years': payment_num / 12,
        })
        
        if remaining_balance <= 0:
            break
            
        # Move to next month
        current_date = next_date
    
    return pd.DataFrame(schedule)

def main():
    st.set_page_config(page_title="Boliglånskalkulator", page_icon="🏡", layout="wide")
    
    st.title('Boliglånskalkulator med eventuelle Utleieinntekter 🏡💰')
    
    # Tabs for basic vs advanced options
    basic_tab, advanced_tab = st.tabs(["Grunnleggende Oppsett", "Avanserte Alternativer"])
    
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
    
    # Calculate amortization schedule
    schedule = calculate_amortization_schedule(
        principal, annual_rate, years, monthly_fee,
        start_date, rental_income, monthly_extra_income, extra_payments,
        reduce_term=reduce_term, reinvest_excess=reinvest_excess
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
    
    # Custom CSS styling with slightly larger font and card-like appearance
    metric_style = """
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 10px; height: 100%;">
        <p style="margin-bottom: 0px; color: #666;">{label}</p>
        <p style="font-size: 1.4em; font-weight: bold; margin-top: 4px; color: {color};">{value}</p>
        <p style="margin-top: 5px; font-size: 0.8em; color: #666;">{description}</p>
    </div>
    """
    
    # Create a more organized metrics display with 3 columns
    summary_tab, details_tab = st.tabs(["Økonomisk Sammendrag", "Detaljerte Tall"])
    
    with summary_tab:
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(metric_style.format(
                label="Månedlig utgift",
                value=format_large_number(effective_monthly_cost),
                description="Din månedlige betaling etter leieinntekter",
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
    
    # Visualizations
    st.subheader('Visualiseringer')
    
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
            'Monthly_Interest_Coverage': 'Rentedekning'
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
        yearly_summary = simple_df.groupby('Year').agg({
            'Payment': 'sum',
            'Principal': 'sum',
            'Interest': 'sum',
            'Extra_Payment': 'sum',
            'Monthly_Extra_Income': 'sum',
            'Rental_Income': 'sum',
            'Monthly_Cost': 'sum'
        }).reset_index()
        
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
            'Percent_Paid': 'Nedbetalt %'
        })
        
        st.dataframe(
            display_yearly,
            use_container_width=True,
            height=400
        )
    
    # Download button for the detailed schedule
    csv = schedule.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="Last ned komplett nedbetalingsplan",
        data=csv,
        file_name="nedbetalingsplan.csv",
        mime="text/csv"
    )

if __name__ == "__main__":
    main()
