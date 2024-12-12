import streamlit as st
import pandas as pd
import numpy as np
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

def calculate_amortization_schedule(principal, annual_rate, years, monthly_fee, start_date, rental_income, monthly_extra_income, extra_payments):
    """Calculate complete amortization schedule with extra payments"""
    monthly_rate = annual_rate / 12 / 100
    num_payments = years * 12
    monthly_payment = calculate_monthly_payment(principal, annual_rate, years)
    
    schedule = []
    remaining_balance = principal
    current_date = start_date
    total_extra_payments = 0
    
    for payment_num in range(1, num_payments + 1):
        # Calculate interest and principal for this payment
        interest_payment = remaining_balance * monthly_rate
        principal_payment = monthly_payment - interest_payment
        
        # Add extra payment if exists for this date
        extra_payment = extra_payments.get(current_date, 0)
        total_extra_payments += extra_payment
        principal_payment += extra_payment + monthly_extra_income  # Add monthly extra income to principal payment
        
        # Calculate effective monthly cost
        monthly_cost = monthly_payment + monthly_fee - rental_income - monthly_extra_income
        
        remaining_balance = max(0, remaining_balance - principal_payment)
        
        schedule.append({
            'Payment_Date': current_date,
            'Payment_Num': payment_num,
            'Payment': monthly_payment,
            'Principal': principal_payment,
            'Interest': interest_payment,
            'Extra_Payment': extra_payment,
            'Monthly_Extra_Income': monthly_extra_income,
            'Remaining_Balance': remaining_balance,
            'Monthly_Fee': monthly_fee,
            'Rental_Income': rental_income,
            'Monthly_Cost': monthly_cost,
            'Years': payment_num / 12,
        })
        
        if remaining_balance <= 0:
            break
            
        current_date = date(current_date.year + ((current_date.month) // 12),
                           ((current_date.month) % 12) + 1,
                           current_date.day)
    
    return pd.DataFrame(schedule)

def main():
    st.title('Boliglån Kalkulator med Utleieinntekter 🏠')
    
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
                                    value=5.4, 
                                    step=0.1)
        
        years = st.number_input('Nedbetalingstid (År)', 
                              min_value=1, 
                              max_value=30, 
                              value=30, 
                              step=1)
    
    with col2:
        rental_income = st.number_input('Månedlig utleieinntekt, avkortet til nedbetaling (NOK)', 
                                      min_value=0, 
                                      value=22500, 
                                      step=500,
                                      format='%d')
        
        monthly_extra_income = st.number_input('Fast månedlig ekstra nedbetaling (NOK)',
                                             min_value=0,
                                             value=0,
                                             step=500,
                                             format='%d')
        
        monthly_fee = st.number_input('Månedlig gebyr til banken (NOK)', 
                                    min_value=0, 
                                    value=60, 
                                    step=5,
                                    format='%d')
        
        start_date = st.date_input('Lånets startdato', 
                                  date(2025, 8, 15))


    # Extra payments input
    st.subheader('Ekstra Innbetalinger')
    
    # Container for adding new extra payments
    with st.expander("Legg til ekstra innbetaling. Velg om du for eksempel skal bruke egenkapital, eller investere bonusen du har fått fra jobb til nedbetaling", expanded=True):
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
                value=100000,
                step=10000,
                format='%d',
                key='extra_payment_amount'
            )
        
        with col3:
            if st.button('Legg til', key='add_payment'):
                # Convert the current extra payments to a string if it exists
                current_payments = st.session_state.get('extra_payments', '')
                
                # Add the new payment
                new_payment = f"{extra_payment_date}, {extra_payment_amount}"
                if current_payments:
                    current_payments = current_payments + '\n' + new_payment
                else:
                    current_payments = new_payment
                
                # Store in session state
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
    
    extra_payments = process_extra_payments(extra_payments_input)
    
    # Calculate amortization schedule
    schedule = calculate_amortization_schedule(
        principal, annual_rate, years, monthly_fee,
        start_date, rental_income, monthly_extra_income, extra_payments
    )
    
    def format_large_number(number):
        # Add thousand separator using Norwegian locale
        formatted_num = f'{abs(number):,.0f}'.replace(',', ' ')  # Replace comma with space for Norwegian style
        if number < 0:
            return f'-{formatted_num} NOK'
        return f'{formatted_num} NOK'

    # Display key metrics
    st.subheader('Nøkkeltall')
    col1, col2, col3, col4 = st.columns(4)

    monthly_payment = calculate_monthly_payment(principal, annual_rate, years)
    effective_monthly_cost = monthly_payment + monthly_fee - rental_income - monthly_extra_income
    total_interest = schedule['Interest'].sum()

    # Calculate total interest we actually pay (after rental income is applied)
    monthly_interest_paid = schedule.apply(lambda row: max(0, row['Interest'] - row['Rental_Income']), axis=1)
    egen_rentekostnad = monthly_interest_paid.sum()


    # Custom CSS styling with slightly larger font
    metric_style = """
    <div style="font-size: 0.9em;">
        <p style="margin-bottom: 0px;">{label}</p>
        <p style="font-size: 1.1em; font-weight: bold; margin-top: 4px;">{value}</p>
    </div>
    """

    with col1:
        st.markdown(metric_style.format(
            label="Månedlig betaling, sum",
            value=format_large_number(monthly_payment)
        ), unsafe_allow_html=True)
    with col2:
        st.markdown(metric_style.format(
            label="Månedlig betaling, minus leie",
            value=format_large_number(effective_monthly_cost)
        ), unsafe_allow_html=True)
    with col3:
        st.markdown(metric_style.format(
            label="Bankens fortjeneste, sum",
            value=format_large_number(total_interest)
        ), unsafe_allow_html=True)
    with col4:
        st.markdown(metric_style.format(
            label="Sum egen rentekostnad",
            value=format_large_number(egen_rentekostnad)
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
        title='Månedlig Rentedekning over Tid',
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

    # Add monthly coverage analysis
    monthly_coverage = schedule.iloc[0]  # First month
    initial_coverage_ratio = monthly_coverage['Interest_Coverage_Ratio']
    initial_coverage_amount = monthly_coverage['Monthly_Interest_Coverage']

#    st.markdown(f"""
#    ### Analyse av Månedlig Rentedekning
#
#    Første måned:
#    - Rentekostnad: {monthly_coverage['Interest']:,.0f} NOK
#    - Leieinntekt: {monthly_coverage['Rental_Income']:,.0f} NOK
#    - Dekningsgrad: {initial_coverage_ratio:.1f}x
#    - Månedlig over/underdekning: {initial_coverage_amount:,.0f} NOK
#
#    Dette betyr at leieinntektene dekker {(initial_coverage_ratio * 100):.1f}% av rentekostnadene hver måned.
#    """)


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
    
    # Monthly breakdown
    fig_monthly = go.Figure()
    fig_monthly.add_trace(go.Bar(
        x=schedule['Payment_Date'][:360],
        y=schedule['Interest'][:360],
        name='Renter'
    ))
    fig_monthly.add_trace(go.Bar(
        x=schedule['Payment_Date'][:360],
        y=schedule['Principal'][:360],
        name='Avdrag'
    ))
    
    fig_monthly.update_layout(
        title='Månedlig Fordeling (30 år)',
        xaxis_title='Dato',
        yaxis_title='Beløp (NOK)',
        barmode='stack',
        hovermode='x'
    )
    
    st.plotly_chart(fig_monthly, use_container_width=True)    

    
    # Detailed table
    st.subheader('Detaljert Nedbetalingsplan')
    
    # Format numbers in the DataFrame
    display_df = schedule.copy()
    numeric_columns = ['Payment', 'Principal', 'Interest', 'Extra_Payment', 
                      'Monthly_Extra_Income', 'Remaining_Balance', 'Monthly_Fee', 
                      'Rental_Income', 'Monthly_Cost']
    
    for col in numeric_columns:
        display_df[col] = display_df[col].apply(lambda x: f'{x:,.0f} NOK')
    
    display_df['Years'] = display_df['Years'].apply(lambda x: f'{x:.2f}')
    
    # Rename columns for display
    display_df = display_df.rename(columns={
        'Payment_Date': 'Dato',
        'Payment_Num': 'Betaling Nr',
        'Payment': 'Innbetaling',
        'Principal': 'Avdrag',
        'Interest': 'Renter',
        'Extra_Payment': 'Ekstra Innbetaling',
        'Monthly_Extra_Income': 'Fast Månedlig Ekstra nedbetaling',
        'Remaining_Balance': 'Gjenstående Balanse',
        'Monthly_Fee': 'Månedlig Gebyr',
        'Rental_Income': 'Leieinntekt til banken',
        'Monthly_Cost': 'Egen innbetaling til banken',
        'Years': 'År'
    })
    
    st.dataframe(display_df, use_container_width=True)
    
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
